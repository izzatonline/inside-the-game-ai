/** Stoppage time reads 90+3', not 93'. */
export const fmtMinute = (m: number) => (m > 90 ? `90+${m - 90}` : String(m))
