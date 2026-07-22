// Common trading currencies with their country code (ISO 3166-1 alpha-2) for
// flag rendering, plus a human-readable name. Used by the currency picker.

export interface CurrencyInfo {
  code: string; // ISO 4217, e.g. "USD"
  name: string;
  /** Country code used to fetch the flag (lowercase). "eu" for the euro. */
  flag: string;
}

export const CURRENCIES: CurrencyInfo[] = [
  { code: "USD", name: "US Dollar", flag: "us" },
  { code: "EUR", name: "Euro", flag: "eu" },
  { code: "GBP", name: "British Pound", flag: "gb" },
  { code: "BDT", name: "Bangladeshi Taka", flag: "bd" },
  { code: "INR", name: "Indian Rupee", flag: "in" },
  { code: "PKR", name: "Pakistani Rupee", flag: "pk" },
  { code: "NPR", name: "Nepalese Rupee", flag: "np" },
  { code: "LKR", name: "Sri Lankan Rupee", flag: "lk" },
  { code: "AED", name: "UAE Dirham", flag: "ae" },
  { code: "SAR", name: "Saudi Riyal", flag: "sa" },
  { code: "QAR", name: "Qatari Riyal", flag: "qa" },
  { code: "KWD", name: "Kuwaiti Dinar", flag: "kw" },
  { code: "BHD", name: "Bahraini Dinar", flag: "bh" },
  { code: "OMR", name: "Omani Rial", flag: "om" },
  { code: "JPY", name: "Japanese Yen", flag: "jp" },
  { code: "CNY", name: "Chinese Yuan", flag: "cn" },
  { code: "HKD", name: "Hong Kong Dollar", flag: "hk" },
  { code: "KRW", name: "South Korean Won", flag: "kr" },
  { code: "SGD", name: "Singapore Dollar", flag: "sg" },
  { code: "MYR", name: "Malaysian Ringgit", flag: "my" },
  { code: "THB", name: "Thai Baht", flag: "th" },
  { code: "IDR", name: "Indonesian Rupiah", flag: "id" },
  { code: "PHP", name: "Philippine Peso", flag: "ph" },
  { code: "VND", name: "Vietnamese Dong", flag: "vn" },
  { code: "AUD", name: "Australian Dollar", flag: "au" },
  { code: "NZD", name: "New Zealand Dollar", flag: "nz" },
  { code: "CAD", name: "Canadian Dollar", flag: "ca" },
  { code: "CHF", name: "Swiss Franc", flag: "ch" },
  { code: "NOK", name: "Norwegian Krone", flag: "no" },
  { code: "SEK", name: "Swedish Krona", flag: "se" },
  { code: "DKK", name: "Danish Krone", flag: "dk" },
  { code: "PLN", name: "Polish Zloty", flag: "pl" },
  { code: "TRY", name: "Turkish Lira", flag: "tr" },
  { code: "RUB", name: "Russian Ruble", flag: "ru" },
  { code: "ZAR", name: "South African Rand", flag: "za" },
  { code: "EGP", name: "Egyptian Pound", flag: "eg" },
  { code: "BRL", name: "Brazilian Real", flag: "br" },
  { code: "MXN", name: "Mexican Peso", flag: "mx" },
];

const CURRENCY_BY_CODE = new Map(CURRENCIES.map((c) => [c.code, c]));

export function findCurrency(code: string): CurrencyInfo | undefined {
  return CURRENCY_BY_CODE.get(code.trim().toUpperCase());
}

export function searchCurrencies(query: string): CurrencyInfo[] {
  const q = query.trim().toLowerCase();
  if (!q) return CURRENCIES;
  return CURRENCIES.filter(
    (c) =>
      c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q),
  );
}

/** flagcdn URL for a 1x flag image (2x available via srcSet). */
export function flagUrl(cc: string, scale: 1 | 2 = 1): string {
  const size = scale === 2 ? "40x30" : "20x15";
  return `https://flagcdn.com/${size}/${cc}.png`;
}
