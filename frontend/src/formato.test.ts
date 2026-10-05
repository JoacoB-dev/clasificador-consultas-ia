import { describe, expect, it } from 'vitest'
import { porcentaje, textoSla, usd } from './formato'

describe('textoSla', () => {
  const ahora = new Date('2026-10-04T12:00:00Z')

  it('muestra horas que faltan', () => {
    expect(textoSla('2026-10-04T15:30:00Z', ahora)).toBe('Vence en 3 h')
  })

  it('muestra cuánto hace que venció', () => {
    expect(textoSla('2026-10-04T11:15:00Z', ahora)).toBe('Vencido hace 45 min')
  })

  it('usa días para plazos largos', () => {
    expect(textoSla('2026-10-07T12:00:00Z', ahora)).toBe('Vence en 3 d')
  })

  it('sin fecha no hay SLA', () => {
    expect(textoSla(null, ahora)).toBe('Sin SLA')
  })
})

describe('porcentaje y usd', () => {
  it('formatea porcentajes y nulos', () => {
    expect(porcentaje(0.875)).toBe('88%')
    expect(porcentaje(null)).toBe('—')
  })

  it('muestra más decimales para montos chicos', () => {
    expect(usd(0.0054)).toBe('US$ 0.0054')
    expect(usd(12.5)).toBe('US$ 12.50')
  })
})
