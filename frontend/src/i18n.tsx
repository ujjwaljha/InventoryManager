import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Lang = "en" | "id";

const STRINGS = {
  en: {
    shopNameFallback: "Warung Pojok",
    shopFloor: "Shop floor",
    operatorTill: "Operator till",
    shop: "Shop",
    order: "Order",
    invoices: "Invoices",
    operator: "Operator",
    home: "Home",
    items: "Items",
    orders: "Orders",
    settings: "Settings",
    more: "More",
    openShop: "Open shop",
    guest: "Guest",
    all: "All",
    searchShop: "Search rice, oil, soap…",
    searchSku: "Search SKU or name",
    add: "Add",
    soldOut: "Sold out",
    inStock: "{qty} {unit} in stock",
    whoShopping: "Who is shopping?",
    whoShoppingHint: "We keep your purchase order on this phone until you place it.",
    name: "Name",
    nameEn: "Name (English)",
    nameId: "Name (Indonesian)",
    phone: "Phone",
    yourName: "Your name",
    mobileNumber: "Mobile number",
    continue: "Continue",
    emptyPo: "Your purchase order is empty",
    emptyPoHint: "Add items from the shop. Stock is held only when you place the order.",
    browseShop: "Browse shop",
    purchaseOrder: "Purchase order",
    each: "each",
    noteForShop: "Note for the shop",
    subtotal: "Subtotal",
    tax: "Tax",
    total: "Total",
    placeHint: "Placing this order will take items off the shelf and raise an invoice.",
    placing: "Placing…",
    placeOrder: "Place order & raise invoice",
    noInvoices: "No invoices yet",
    noInvoicesHint: "Place a purchase order and an invoice will appear here.",
    yourInvoices: "Your invoices",
    loadingInvoice: "Loading invoice…",
    backInvoices: "← Invoices",
    backItems: "← Items",
    printSave: "Print / save",
    print: "Print",
    invoice: "Invoice",
    billTo: "Bill to",
    item: "Item",
    qty: "Qty",
    price: "Price",
    amount: "Amount",
    loading: "Loading…",
    skus: "SKUs",
    unitsOnHand: "Units on hand",
    lowStock: "Low stock",
    todaysSales: "Today's sales",
    ordersToday: "Orders today",
    nothingLow: "Nothing below reorder point.",
    recentMoves: "Recent stock moves",
    newItem: "New item",
    location: "Location",
    purchaseOrders: "Purchase orders",
    onHand: "On hand: {qty} {unit}",
    belowReorder: "Below reorder point ({point})",
    details: "Details",
    description: "Description",
    descriptionEn: "Description (English)",
    descriptionId: "Description (Indonesian)",
    sellPrice: "Sell price (IDR)",
    cost: "Cost (IDR)",
    reorderPoint: "Reorder point",
    notes: "Notes",
    save: "Save",
    stock: "Stock",
    stockHint: "Sales go through Place order. Use these for deliveries, counts, and shrinkage.",
    quantity: "Quantity",
    reason: "Reason",
    reasonPlaceholder: "Supplier delivery, count, breakage…",
    receiveIn: "Receive in",
    setCount: "Set count",
    shrinkage: "Shrinkage",
    history: "History",
    when: "When",
    kind: "Kind",
    delta: "Delta",
    after: "After",
    archiveItem: "Archive item",
    openingQty: "Opening quantity",
    unit: "Unit",
    create: "Create",
    markPaid: "Mark paid",
    cancelOrder: "Cancel order",
    shopSettings: "Shop settings",
    phoneAccess: "Phone access",
    phoneAccessHint: "On the same Wi‑Fi, open this address in the phone browser:",
    shopName: "Shop name",
    address: "Address",
    currency: "Currency",
    currencyValue: "Indonesian Rupiah (IDR) · Rp",
    taxPct: "Tax %",
    saved: "Saved.",
    exportCsv: "Export items CSV",
    downloadBackup: "Download SQLite backup",
    status_draft: "draft",
    status_placed: "placed",
    status_cancelled: "cancelled",
    status_issued: "issued",
    status_paid: "paid",
    status_void: "void",
    kind_in: "in",
    kind_out: "out",
    kind_adjust: "count",
    couldNotAdd: "Could not add",
    updateFailed: "Update failed",
    onlyLeft: "{name}: only {available} left",
    shortageLine: "{name}: need {requested}, have {available}",
    couldNotPlace: "Could not place order",
    movementFailed: "Movement failed",
    couldNotCreate: "Could not create",
    sku: "SKU",
    language: "Language",
  },
  id: {
    shopNameFallback: "Warung Pojok",
    shopFloor: "Belanja",
    operatorTill: "Kasir",
    shop: "Toko",
    order: "Pesanan",
    invoices: "Faktur",
    operator: "Kasir",
    home: "Beranda",
    items: "Barang",
    orders: "Pesanan",
    settings: "Pengaturan",
    more: "Lainnya",
    openShop: "Buka toko",
    guest: "Tamu",
    all: "Semua",
    searchShop: "Cari beras, minyak, sabun…",
    searchSku: "Cari SKU atau nama",
    add: "Tambah",
    soldOut: "Stok habis",
    inStock: "{qty} {unit} stok",
    whoShopping: "Siapa yang belanja?",
    whoShoppingHint: "Pesanan disimpan di HP ini sampai Anda menempatkannya.",
    name: "Nama",
    nameEn: "Nama (Inggris)",
    nameId: "Nama (Indonesia)",
    phone: "Telepon",
    yourName: "Nama Anda",
    mobileNumber: "Nomor HP",
    continue: "Lanjut",
    emptyPo: "Pesanan Anda masih kosong",
    emptyPoHint: "Tambah barang dari toko. Stok baru berkurang setelah pesanan ditempatkan.",
    browseShop: "Lihat toko",
    purchaseOrder: "Pesanan pembelian",
    each: "per item",
    noteForShop: "Catatan untuk toko",
    subtotal: "Subtotal",
    tax: "Pajak",
    total: "Total",
    placeHint: "Menempatkan pesanan akan mengurangi stok dan menerbitkan faktur.",
    placing: "Memproses…",
    placeOrder: "Pesan & terbitkan faktur",
    noInvoices: "Belum ada faktur",
    noInvoicesHint: "Tempatkan pesanan, lalu faktur akan muncul di sini.",
    yourInvoices: "Faktur Anda",
    loadingInvoice: "Memuat faktur…",
    backInvoices: "← Faktur",
    backItems: "← Barang",
    printSave: "Cetak / simpan",
    print: "Cetak",
    invoice: "Faktur",
    billTo: "Tagihan kepada",
    item: "Barang",
    qty: "Jml",
    price: "Harga",
    amount: "Jumlah",
    loading: "Memuat…",
    skus: "SKU",
    unitsOnHand: "Unit di gudang",
    lowStock: "Stok menipis",
    todaysSales: "Penjualan hari ini",
    ordersToday: "Pesanan hari ini",
    nothingLow: "Tidak ada barang di bawah batas stok.",
    recentMoves: "Mutasi stok terbaru",
    newItem: "Barang baru",
    location: "Lokasi",
    purchaseOrders: "Pesanan pembelian",
    onHand: "Stok: {qty} {unit}",
    belowReorder: "Di bawah batas stok ({point})",
    details: "Detail",
    description: "Deskripsi",
    descriptionEn: "Deskripsi (Inggris)",
    descriptionId: "Deskripsi (Indonesia)",
    sellPrice: "Harga jual (IDR)",
    cost: "Harga modal (IDR)",
    reorderPoint: "Batas stok minimum",
    notes: "Catatan",
    save: "Simpan",
    stock: "Stok",
    stockHint: "Penjualan lewat Pesan. Ini untuk penerimaan, stok opname, dan susut.",
    quantity: "Jumlah",
    reason: "Alasan",
    reasonPlaceholder: "Kiriman pemasok, stok opname, rusak…",
    receiveIn: "Terima barang",
    setCount: "Stok opname",
    shrinkage: "Susut / rusak",
    history: "Riwayat",
    when: "Waktu",
    kind: "Jenis",
    delta: "Selisih",
    after: "Sesudah",
    archiveItem: "Arsipkan barang",
    openingQty: "Stok awal",
    unit: "Satuan",
    create: "Buat",
    markPaid: "Tandai lunas",
    cancelOrder: "Batalkan pesanan",
    shopSettings: "Pengaturan toko",
    phoneAccess: "Akses HP",
    phoneAccessHint: "Di Wi‑Fi yang sama, buka alamat ini di peramban HP:",
    shopName: "Nama toko",
    address: "Alamat",
    currency: "Mata uang",
    currencyValue: "Rupiah Indonesia (IDR) · Rp",
    taxPct: "Pajak %",
    saved: "Tersimpan.",
    exportCsv: "Ekspor CSV barang",
    downloadBackup: "Unduh cadangan SQLite",
    status_draft: "draf",
    status_placed: "dipesan",
    status_cancelled: "dibatalkan",
    status_issued: "terbit",
    status_paid: "lunas",
    status_void: "batal",
    kind_in: "masuk",
    kind_out: "keluar",
    kind_adjust: "opname",
    couldNotAdd: "Tidak bisa menambah",
    updateFailed: "Gagal memperbarui",
    onlyLeft: "{name}: sisa {available}",
    shortageLine: "{name}: perlu {requested}, tersedia {available}",
    couldNotPlace: "Tidak bisa menempatkan pesanan",
    movementFailed: "Mutasi gagal",
    couldNotCreate: "Tidak bisa membuat",
    sku: "SKU",
    language: "Bahasa",
  },
} as const;

export type MsgKey = keyof typeof STRINGS.en;

type Vars = Record<string, string | number>;

type I18nValue = {
  locale: Lang;
  setLocale: (lang: Lang) => void;
  t: (key: MsgKey, vars?: Vars) => string;
  pick: (en: string, id?: string | null) => string;
  localeTag: string;
};

const I18nContext = createContext<I18nValue | null>(null);

function initialLocale(): Lang {
  try {
    const stored = localStorage.getItem("im_locale");
    if (stored === "en" || stored === "id") return stored;
  } catch {
    /* ignore */
  }
  if (typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("id")) {
    return "id";
  }
  return "id";
}

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? ""));
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Lang>(initialLocale);

  useEffect(() => {
    document.documentElement.lang = locale === "id" ? "id" : "en";
    document.title = "Warung Pojok";
    try {
      localStorage.setItem("im_locale", locale);
    } catch {
      /* ignore */
    }
  }, [locale]);

  const value = useMemo<I18nValue>(() => {
    const setLocale = (lang: Lang) => setLocaleState(lang);
    const t = (key: MsgKey, vars?: Vars) => interpolate(STRINGS[locale][key], vars);
    const pick = (en: string, id?: string | null) => (locale === "id" ? id || en : en);
    return {
      locale,
      setLocale,
      t,
      pick,
      localeTag: locale === "id" ? "id-ID" : "en-GB",
    };
  }, [locale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within LocaleProvider");
  return ctx;
}

export function LanguageSwitch() {
  const { locale, setLocale, t } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label={t("language")}>
      <button type="button" className={locale === "en" ? "on" : ""} onClick={() => setLocale("en")}>
        EN
      </button>
      <button type="button" className={locale === "id" ? "on" : ""} onClick={() => setLocale("id")}>
        ID
      </button>
    </div>
  );
}
