// Inside the Game on Azure: Container Apps + Event Hubs, Entra-only auth (managed identity).
// Unvalidated draft: run `az bicep build` / `az deployment group what-if` before deploying.
param location string = resourceGroup().location
param prefix string = 'itg'
@description('Container image, e.g. <acr>.azurecr.io/itg:latest')
param image string
param acrName string
param foundryProjectEndpoint string = ''
param foundryModel string = ''

var suffix = uniqueString(resourceGroup().id)
var receiverRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde') // Azure Event Hubs Data Receiver
var senderRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2b629674-e913-4c01-ae53-ef4638d8f975')   // Azure Event Hubs Data Sender
var acrPullRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')  // AcrPull

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-id-${suffix}'
  location: location
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs-${suffix}'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource ns 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: '${prefix}-ns-${suffix}'
  location: location
  sku: { name: 'Standard', tier: 'Standard', capacity: 1 }
  properties: { disableLocalAuth: true }
}

resource hub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: ns
  name: 'match-events'
  properties: { partitionCount: 2, messageRetentionInDays: 1 }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: acrName }

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, identity.id, acrPullRole)
  properties: { roleDefinitionId: acrPullRole, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource recv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: hub
  name: guid(hub.id, identity.id, receiverRole)
  properties: { roleDefinitionId: receiverRole, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource send 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: hub
  name: guid(hub.id, identity.id, senderRole)
  properties: { roleDefinitionId: senderRole, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
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
  dependsOn: [ pull ]
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
          { name: 'ITG_INGEST', value: 'eventhubs' }
          { name: 'EVENTHUB_NAMESPACE', value: '${ns.name}.servicebus.windows.net' }
          { name: 'EVENTHUB_NAME', value: hub.name }
          { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
          { name: 'FOUNDRY_MODEL', value: foundryModel }
        ]
        probes: [ { type: 'Liveness', httpGet: { path: '/api/config', port: 8000 } } ]
      } ]
      scale: { minReplicas: 1, maxReplicas: 3, rules: [ { name: 'http', http: { metadata: { concurrentRequests: '50' } } } ] }
    }
  }
}

output url string = 'https://${app.properties.configuration.ingress.fqdn}'
output eventHubNamespace string = '${ns.name}.servicebus.windows.net'
