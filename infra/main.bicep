// Inside the Game on Azure Container Apps, keyless: the app reaches the Foundry model through a managed identity
// (Cognitive Services OpenAI User role) and reads the recap aloud with Azure AI Speech on the same resource (Speech User role),
// pulls its image from ACR through the same identity, scales to zero when idle,
// and sends logs to Log Analytics. Deploy into the resource group that holds the Foundry (AI Services) resource.
param location string = resourceGroup().location
param prefix string = 'itg'
@description('Container image, e.g. <acr>.azurecr.io/itg:latest')
param image string
@description('Existing Azure Container Registry in this resource group')
param acrName string
@description('Existing Foundry / Azure AI Services account in this resource group (the model host)')
param aiAccountName string
@description('Model deployment name, e.g. gpt-5-mini-1')
param modelDeployment string
@description('Global cap on model calls per hour; above it the app uses grounded templates (protects the bill)')
param maxModelCallsPerHour int = 1500

var suffix = uniqueString(resourceGroup().id)
var acrPullRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var openAiUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
var speechUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'f2dc8367-1007-4938-bd23-fe263f013447')

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-id-${suffix}'
  location: location
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs-${suffix}'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: acrName }
resource ai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = { name: aiAccountName }

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, identity.id, acrPullRole)
  properties: { roleDefinitionId: acrPullRole, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource modelUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: ai
  name: guid(ai.id, identity.id, openAiUserRole)
  properties: { roleDefinitionId: openAiUserRole, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource speechUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: ai
  name: guid(ai.id, identity.id, speechUserRole)
  properties: { roleDefinitionId: speechUserRole, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env-${suffix}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: { customerId: logs.properties.customerId, sharedKey: logs.listKeys().primarySharedKey }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-app'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  dependsOn: [ pull, modelUser, speechUser ]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8000, transport: 'auto' }
      registries: [ { server: acr.properties.loginServer, identity: identity.id } ]
    }
    template: {
      containers: [ {
        name: 'itg'
        image: image
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
          { name: 'AZURE_OPENAI_ENDPOINT', value: ai.properties.endpoint }
          { name: 'AZURE_OPENAI_DEPLOYMENT', value: modelDeployment }
          { name: 'ITG_MAX_MODEL_CALLS_PER_HOUR', value: string(maxModelCallsPerHour) }
          { name: 'SPEECH_REGION', value: location }
          { name: 'SPEECH_RESOURCE_ID', value: ai.id }
        ]
        probes: [ { type: 'Liveness', httpGet: { path: '/api/config', port: 8000 }, initialDelaySeconds: 10 } ]
      } ]
      scale: { minReplicas: 0, maxReplicas: 2, rules: [ { name: 'http', http: { metadata: { concurrentRequests: '50' } } } ] }
    }
  }
}

output url string = 'https://${app.properties.configuration.ingress.fqdn}'
