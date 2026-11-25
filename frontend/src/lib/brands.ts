/**
 * Reconhecimento de marcas (estabelecimentos e bancos) para exibir ícones.
 *
 * Privacidade: os ícones vêm do pacote local `simple-icons` (CC0) — nenhum nome de
 * estabelecimento é enviado a serviço externo. Marcas que não estão no pacote
 * (bancos e algumas empresas pediram remoção) usam monograma na cor da marca.
 */
import {
  siAirbnb,
  siAliexpress,
  siApple,
  siAppletv,
  siBurgerking,
  siCarrefour,
  siCrunchyroll,
  siDeezer,
  siDiscord,
  siDuolingo,
  siGoogle,
  siGoogleplay,
  siHbo,
  siIcloud,
  siIfood,
  siKfc,
  siMax,
  siMcdonalds,
  siMercadopago,
  siNetflix,
  siNubank,
  siParamountplus,
  siPaypal,
  siPicpay,
  siPlaystation,
  siShell,
  siShopee,
  siSpotify,
  siStarbucks,
  siSteam,
  siTwitch,
  siUber,
  siVivo,
  siYoutube,
  siYoutubemusic,
  type SimpleIcon,
} from 'simple-icons'

export interface Brand {
  key: string
  label: string
  /** Cor de fundo do avatar (hex sem '#'). */
  color: string
  /** Ícone vetorial; sem ele, usa `monogram`. */
  icon?: SimpleIcon
  monogram?: string
}

interface Rule extends Brand {
  /** Termos normalizados (sem acento, minúsculos) que identificam a marca. */
  terms: string[]
}

const fromIcon = (key: string, icon: SimpleIcon, terms: string[], label = icon.title): Rule => ({
  key,
  label,
  color: icon.hex,
  icon,
  terms,
})
const mono = (key: string, label: string, color: string, monogram: string, terms: string[]): Rule => ({
  key,
  label,
  color,
  monogram,
  terms,
})

// Ordem importa: termos mais específicos antes dos genéricos (ex.: "youtube music" antes de "youtube").
const RULES: Rule[] = [
  // Streaming e assinaturas
  fromIcon('netflix', siNetflix, ['netflix']),
  fromIcon('spotify', siSpotify, ['spotify']),
  fromIcon('youtubemusic', siYoutubemusic, ['youtube music', 'yt music']),
  fromIcon('youtube', siYoutube, ['youtube', 'yt premium']),
  fromIcon('max', siMax, ['hbo max', 'max.com', 'hbomax']),
  fromIcon('hbo', siHbo, ['hbo']),
  fromIcon('paramount', siParamountplus, ['paramount']),
  fromIcon('crunchyroll', siCrunchyroll, ['crunchyroll']),
  fromIcon('deezer', siDeezer, ['deezer']),
  fromIcon('appletv', siAppletv, ['apple tv']),
  fromIcon('icloud', siIcloud, ['icloud']),
  fromIcon('apple', siApple, ['apple', 'app store', 'itunes']),
  fromIcon('googleplay', siGoogleplay, ['google play']),
  fromIcon('google', siGoogle, ['google']),
  fromIcon('twitch', siTwitch, ['twitch']),
  fromIcon('discord', siDiscord, ['discord', 'nitro']),
  fromIcon('duolingo', siDuolingo, ['duolingo']),
  fromIcon('steam', siSteam, ['steam']),
  fromIcon('playstation', siPlaystation, ['playstation', 'psn']),
  mono('disney', 'Disney+', '113CCF', 'D+', ['disney']),
  mono('prime', 'Prime Video', '00A8E1', 'P', ['prime video', 'amazon prime']),
  mono('globoplay', 'Globoplay', 'F33B23', 'G', ['globoplay', 'globo']),
  mono('chatgpt', 'ChatGPT', '10A37F', 'AI', ['chatgpt', 'openai']),
  mono('microsoft', 'Microsoft', '5E5E5E', 'MS', ['microsoft', 'xbox', 'office 365', 'microsoft 365']),
  mono('adobe', 'Adobe', 'DA1F26', 'A', ['adobe']),
  mono('canva', 'Canva', '00C4CC', 'C', ['canva']),
  // Delivery, transporte e compras
  fromIcon('ifood', siIfood, ['ifood']),
  fromIcon('uber', siUber, ['uber']),
  mono('99', '99', 'FFDD00', '99', ['99app', '99 pop', '99pop', ' 99 ']),
  mono('rappi', 'Rappi', 'FF441F', 'R', ['rappi']),
  mono('amazon', 'Amazon', 'FF9900', 'a', ['amazon']),
  mono('mercadolivre', 'Mercado Livre', 'FFE600', 'ML', ['mercado livre', 'mercadolivre']),
  fromIcon('shopee', siShopee, ['shopee']),
  fromIcon('aliexpress', siAliexpress, ['aliexpress']),
  mono('shein', 'Shein', '222222', 'S', ['shein']),
  mono('magalu', 'Magalu', '0086FF', 'M', ['magalu', 'magazine luiza']),
  fromIcon('airbnb', siAirbnb, ['airbnb']),
  // Alimentação e varejo
  fromIcon('mcdonalds', siMcdonalds, ['mcdonald', 'mc donald', 'mequi']),
  fromIcon('burgerking', siBurgerking, ['burger king']),
  fromIcon('kfc', siKfc, ['kfc']),
  fromIcon('starbucks', siStarbucks, ['starbucks']),
  fromIcon('carrefour', siCarrefour, ['carrefour']),
  fromIcon('shell', siShell, ['shell']),
  // Telefonia
  fromIcon('vivo', siVivo, ['vivo']),
  mono('claro', 'Claro', 'DA291C', 'C', ['claro']),
  mono('tim', 'TIM', '004691', 'TIM', [' tim ', 'tim brasil']),
  // Bancos e carteiras (também usados para os cartões)
  fromIcon('nubank', siNubank, ['nubank', 'nu pagamentos', ' nu ']),
  fromIcon('mercadopago', siMercadopago, ['mercado pago', 'mercadopago']),
  fromIcon('picpay', siPicpay, ['picpay']),
  fromIcon('paypal', siPaypal, ['paypal']),
  mono('itau', 'Itaú', 'EC7000', 'it', ['itau', 'personnalite']),
  mono('inter', 'Inter', 'FF7A00', 'in', ['banco inter', 'inter ']),
  mono('c6', 'C6 Bank', '242424', 'C6', ['c6 bank', 'c6bank', 'c6 ']),
  mono('santander', 'Santander', 'EC0000', 'S', ['santander']),
  mono('bradesco', 'Bradesco', 'CC092F', 'B', ['bradesco']),
  mono('bb', 'Banco do Brasil', 'FCFC30', 'BB', ['banco do brasil', 'bb ', 'ourocard']),
  mono('caixa', 'Caixa', '005CA9', 'CX', ['caixa']),
  mono('xp', 'XP', '000000', 'XP', ['xp investimentos', 'xp ']),
  mono('btg', 'BTG Pactual', '0B2E59', 'BTG', ['btg']),
  mono('neon', 'Neon', '00E5FF', 'N', ['neon']),
  mono('will', 'Will Bank', 'FFE500', 'W', ['will bank', 'willbank']),
]

export function normalize(text: string): string {
  return ` ${text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9.+ ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()} `
}

const cache = new Map<string, Brand | null>()

/** Primeira marca reconhecida entre os textos (ex.: estabelecimento, depois descrição). */
export function resolveBrand(...texts: (string | null | undefined)[]): Brand | null {
  for (const t of texts) {
    if (!t) continue
    const n = normalize(t)
    if (cache.has(n)) {
      const hit = cache.get(n)
      if (hit) return hit
      continue
    }
    // `n` vem com espaço nas pontas, então termos curtos com espaço (" nu ", "c6 ") casam só palavra inteira.
    const rule = RULES.find((r) => r.terms.some((term) => n.includes(term)))
    const brand = rule ? { key: rule.key, label: rule.label, color: rule.color, icon: rule.icon, monogram: rule.monogram } : null
    cache.set(n, brand)
    if (brand) return brand
  }
  return null
}

/** Texto legível sobre a cor de fundo (preto em cores claras, branco nas escuras). */
export function contrastInk(hex: string): string {
  const v = parseInt(hex, 16)
  const r = (v >> 16) & 255
  const g = (v >> 8) & 255
  const b = v & 255
  // Luminância relativa aproximada (sRGB) — só para escolher a tinta.
  const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
  return lum > 0.6 ? '#111111' : '#FFFFFF'
}

/** Iniciais para nomes sem marca reconhecida. */
export function initials(name: string): string {
  const words = name.replace(/[^\p{L}\p{N} ]/gu, ' ').trim().split(/\s+/).filter(Boolean)
  if (!words.length) return '?'
  return (words.length === 1 ? words[0].slice(0, 2) : words[0][0] + words[1][0]).toUpperCase()
}
