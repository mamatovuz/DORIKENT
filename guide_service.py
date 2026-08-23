"""DoriKent test boti uchun to'liq PDF qo'llanma yaratuvchi (fpdf2)."""
from io import BytesIO

from fpdf import FPDF
from fpdf.enums import XPos, YPos


def _mc(pdf, w, h, txt, align="L"):
    """Kursorni har doim keyingi qatorning chap chetiga qo'yadigan multi_cell."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w, h, txt, align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# Yadro shrift (Helvetica) latin-1 kodlashda ishlaydi. O'zbek lotin matni mos.
def _s(text: str) -> str:
    """Latin-1 ga sig'maydigan belgilarni xavfsiz almashtiradi."""
    repl = {
        "’": "'", "‘": "'", "ʻ": "'", "ʼ": "'",
        "–": "-", "—": "-", "“": '"', "”": '"',
        "…": "...", "•": "-",
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class Guide(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 6, _s("DoriKent test boti - Qo'llanma"), align="R")
        self.ln(8)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 8, _s(f"- {self.page_no()} -"), align="C")


def _h1(pdf: Guide, text: str):
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(20, 60, 120)
    _mc(pdf, 0, 8, _s(text))
    pdf.set_draw_color(20, 60, 120)
    pdf.set_line_width(0.5)
    y = pdf.get_y() + 1
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(4)
    pdf.set_text_color(0)


def _h2(pdf: Guide, text: str):
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(40, 40, 40)
    _mc(pdf, 0, 7, _s(text))
    pdf.ln(1)
    pdf.set_text_color(0)


def _p(pdf: Guide, text: str):
    pdf.set_font("Helvetica", "", 11)
    _mc(pdf, 0, 6, _s(text))
    pdf.ln(1)


def _bullets(pdf: Guide, items: list[str]):
    pdf.set_font("Helvetica", "", 11)
    for it in items:
        _mc(pdf, 0, 6, _s(f"-  {it}"))
    pdf.ln(1)


def _steps(pdf: Guide, items: list[str]):
    pdf.set_font("Helvetica", "", 11)
    for i, it in enumerate(items, start=1):
        _mc(pdf, 0, 6, _s(f"{i}.  {it}"))
    pdf.ln(1)


def build_guide_pdf() -> BytesIO:
    pdf = Guide(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(18, 16, 18)
    pdf.add_page()

    # ---- Sarlavha sahifasi ----
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(20, 60, 120)
    _mc(pdf, 0, 12, _s("DoriKent"), align="C")
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0)
    _mc(pdf, 0, 10, _s("Xodimlar test boti"), align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 14)
    _mc(pdf, 0, 8, _s("To'liq foydalanuvchi qo'llanmasi"), align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(90)
    _mc(pdf, 0, 6, _s("Ushbu qo'llanma bot bilan ishlashni ikki qism bo'yicha tushuntiradi: "
                      "XODIM (mijoz) uchun va ADMIN uchun."), align="C")
    pdf.set_text_color(0)

    # ---- Mundarija ----
    pdf.add_page()
    _h1(pdf, "Mundarija")
    _bullets(pdf, [
        "1. Umumiy ma'lumot",
        "2. Xodim (mijoz) uchun qo'llanma",
        "   2.1. Botni ishga tushirish va ro'yxatdan o'tish",
        "   2.2. Profil va uni tahrirlash",
        "   2.3. Testni topshirish",
        "   2.4. Natijalarni ko'rish",
        "3. Admin uchun qo'llanma",
        "   3.1. Admin panelga kirish",
        "   3.2. Test yaratish (Excel yuklash)",
        "   3.3. Testlarni boshqarish (faollashtirish / to'xtatish / o'chirish)",
        "   3.4. Testni xodimlarga yuborish",
        "   3.5. Xodimlar va ularning profillari",
        "   3.6. Natijalar",
        "   3.7. Sozlamalar va AI kalitlari",
        "   3.8. Yangi admin qo'shish",
        "4. Muhim eslatmalar",
    ])

    # ---- 1. Umumiy ----
    pdf.add_page()
    _h1(pdf, "1. Umumiy ma'lumot")
    _p(pdf, "DoriKent test boti - bu kompaniya xodimlarining bilimini tekshirish uchun "
            "mo'ljallangan Telegram bot. Bot ikki turdagi foydalanuvchi bilan ishlaydi:")
    _bullets(pdf, [
        "Xodim (mijoz): ro'yxatdan o'tadi, o'ziga tayinlangan/faol testlarni topshiradi va "
        "natijalarini ko'radi.",
        "Admin: testlar yaratadi, boshqaradi, xodimlarni va natijalarni kuzatadi, sozlamalarni "
        "o'zgartiradi.",
    ])
    _p(pdf, "Bot savollarga noto'g'ri javob variantlarini avtomatik (sun'iy intellekt yoki "
            "AI-siz generator yordamida) yaratishi mumkin. AI kalitlari admin panelidan kiritiladi.")

    # ---- 2. Xodim ----
    pdf.add_page()
    _h1(pdf, "2. Xodim (mijoz) uchun qo'llanma")

    _h2(pdf, "2.1. Botni ishga tushirish va ro'yxatdan o'tish")
    _p(pdf, "Botni birinchi marta ochganda /start tugmasini bosing. Birinchi kirishda bot sizni "
            "qisqa ro'yxatdan o'tkazadi. Quyidagi ma'lumotlar ketma-ket so'raladi:")
    _steps(pdf, [
        "Ism va familiya - bir qatorda birga yoziladi. Masalan: Aziz Azizov.",
        "Jinsi - ekrandagi tugmalardan tanlanadi: Erkak yoki Ayol.",
        "Tug'ilgan kun - majburiy ravishda kun.oy.yil ko'rinishida kiritiladi. "
        "Masalan: 05.09.1998. Noto'g'ri format qabul qilinmaydi.",
        "Ish staji - necha yildan beri shu sohada ishlayotganingiz (faqat son). Masalan: 5.",
        "Profil rasmi - oxirgi 15 kun ichida tushgan rasmingizni surat (foto) sifatida yuboring.",
    ])
    _p(pdf, "Ro'yxatdan o'tib bo'lgach, botning asosiy menyusi paydo bo'ladi. Keyingi kirishlarda "
            "qayta ro'yxatdan o'tish talab qilinmaydi.")

    _h2(pdf, "2.2. Profil va uni tahrirlash")
    _p(pdf, "'Mening profilim' tugmasi orqali o'z ma'lumotlaringizni ko'rasiz: rasm, ism, "
            "familiya, jinsi, tug'ilgan kun, yosh (avtomatik hisoblanadi) va ish staji.")
    _p(pdf, "Profilni tahrirlash uchun 'Tahrirlash' tugmasini bosing. So'ng o'zgartirmoqchi "
            "bo'lgan maydonni tanlaysiz:")
    _bullets(pdf, [
        "Ism-familiya",
        "Jinsi",
        "Tug'ilgan kun",
        "Ish staji",
        "Rasm",
    ])
    _p(pdf, "Muhim: profil ma'lumotlarini haftada faqat 1 marta o'zgartirish mumkin. Bir marta "
            "o'zgartirilgach, keyingi o'zgartirishgacha 7 kun kutish kerak bo'ladi.")

    _h2(pdf, "2.3. Testni topshirish")
    _steps(pdf, [
        "'Testni boshlash' tugmasini bosing. Sizga ochiq (faol) testlar ro'yxati chiqadi.",
        "Kerakli test ostidagi 'Boshlash' tugmasini bosing.",
        "Har bir savolga variantli javob beriladi. Har bir savol uchun vaqt chegarasi bor.",
        "Vaqt tugasa yoki javob berilsa, keyingi savolga o'tiladi.",
        "Test yakunida natijangiz (agar admin ruxsat bergan bo'lsa) ko'rsatiladi.",
    ])
    _p(pdf, "Agar admin 'qayta topshirish'ga ruxsat bermagan bo'lsa, testni faqat bir marta "
            "topshirasiz. Ruxsat bo'lsa, o'ta olmagan testni qayta topshirishingiz mumkin.")

    _h2(pdf, "2.4. Natijalarni ko'rish")
    _p(pdf, "'Mening natijalarim' tugmasi orqali o'zingiz topshirgan testlar va olgan foizli "
            "natijalaringizni ko'rasiz. Yashil belgi - o'tgan, qizil belgi - o'ta olmagan testni "
            "bildiradi.")

    # ---- 3. Admin ----
    pdf.add_page()
    _h1(pdf, "3. Admin uchun qo'llanma")

    _h2(pdf, "3.1. Admin panelga kirish")
    _p(pdf, "Admin huquqiga ega foydalanuvchi /start bosganda to'g'ridan-to'g'ri admin paneli "
            "ochiladi. Admin menyusidagi bo'limlar:")
    _bullets(pdf, [
        "Excel yuklash - yangi test yaratish.",
        "Shablon olish - savollar uchun tayyor Excel shablonini olish.",
        "Testlar - mavjud testlarni boshqarish.",
        "Xodimlar - ro'yxatdan o'tgan xodimlar va ularning profillari.",
        "Natijalar - barcha natijalar va ularni Excel'ga yuklab olish.",
        "Test yuborish - testni tanlangan xodimlarga jo'natish.",
        "Sozlamalar - standart qiymatlar va AI kalitlari.",
        "AI holati - AI ulanish holatini ko'rish.",
        "Adminlar - yangi admin qo'shish.",
        "Qo'llanma - shu PDF hujjatni olish.",
    ])

    _h2(pdf, "3.2. Test yaratish (Excel yuklash)")
    _steps(pdf, [
        "'Shablon olish' orqali Excel shablonini yuklab oling.",
        "Shablonga savollarni to'ldiring. Ustunlar: Savol | To'g'ri javob | Noto'g'ri 1 | 2 | 3.",
        "Noto'g'ri variantlarni bo'sh qoldirsangiz, bot ularni AI (yoki AI-siz generator) "
        "yordamida avtomatik yaratadi.",
        "'Excel yuklash' tugmasini bosib, test nomi, savollar soni, o'tish bali va har bir "
        "savolga ajratiladigan vaqtni kiriting (yoki '-' yuborib standart qiymatni oling).",
        "Tayyorlangan Excel faylni yuboring. Bot uni o'qib, variantlarni tayyorlaydi.",
        "'Ko'rish' orqali tekshiring va 'Tasdiqlash' bilan testni saqlang.",
    ])

    _h2(pdf, "3.3. Testlarni boshqarish")
    _p(pdf, "'Testlar' bo'limida har bir test ustida quyidagi amallar mavjud:")
    _bullets(pdf, [
        "Tahrirlash - test nomi, savollar soni, o'tish bali, vaqt va boshqa parametrlarni "
        "o'zgartirish.",
        "Ko'rish - testdagi savollar va javob variantlarini ko'rish.",
        "Faollashtirish - testni yoqadi. Faollashtirilgan testni ro'yxatdan o'tgan barcha "
        "xodimlar topshira oladi.",
        "To'xtatish (pauza) - testni vaqtincha o'chiradi. Test o'chib ketmaydi, ammo xodimlar "
        "uni topshira olmaydi. Keyin qayta faollashtirish mumkin.",
        "O'chirish - testni butunlay o'chiradi va testlar ro'yxatidan olib tashlaydi. Bu amalni "
        "orqaga qaytarib bo'lmaydi.",
    ])

    _h2(pdf, "3.4. Testni xodimlarga yuborish")
    _steps(pdf, [
        "'Test yuborish' tugmasini bosing yoki test kartasidagi 'Xodimlarga yuborish'ni tanlang.",
        "Kerakli testni tanlang.",
        "Xodimlarni belgilang (yoki 'Hammasini tanlash').",
        "'Yuborish' tugmasini bosing. Test avtomatik faollashadi va tanlangan xodimlarga "
        "xabar boradi.",
    ])
    _p(pdf, "Eslatma: test faollashtirilgan bo'lsa, u ro'yxatdan o'tgan barcha xodimlarga ochiq "
            "bo'ladi. Yuborish esa xodimlarga qo'shimcha xabar (bildirishnoma) jo'natadi.")

    _h2(pdf, "3.5. Xodimlar va ularning profillari")
    _p(pdf, "'Xodimlar' bo'limida ro'yxatdan o'tgan barcha xodimlar ko'rinadi. Xodim ustiga "
            "bosilganda uning to'liq kartasi ochiladi: profil rasmi, ism-familiya, jinsi, "
            "tug'ilgan kun, yoshi, ish staji hamda test statistikasi (topshirilgan testlar, "
            "o'rtacha natija, o'tgan testlar va oxirgi natijalar).")

    _h2(pdf, "3.6. Natijalar")
    _p(pdf, "'Natijalar' bo'limida oxirgi natijalar ro'yxati ko'rinadi. Shuningdek, barcha "
            "natijalar Excel fayl ko'rinishida avtomatik yuklab beriladi.")

    _h2(pdf, "3.7. Sozlamalar va AI kalitlari")
    _p(pdf, "'Sozlamalar' bo'limida yangi testlar uchun standart qiymatlarni belgilaysiz: "
            "savollar soni, o'tish bali, savolga vaqt, qayta topshirish va natijani ko'rsatish.")
    _p(pdf, "Shu bo'limda AI kalitlarini qo'lda kiritasiz:")
    _bullets(pdf, [
        "Gemini API kaliti - Google Gemini uchun.",
        "ChatGPT (OpenAI) API kaliti - OpenAI uchun.",
    ])
    _p(pdf, "Kalitni kiritish uchun tegishli tugmani bosing va kalitni to'liq nusxalab yuboring. "
            "Kalitni o'chirish uchun '-' belgisini yuboring. Ikkala kalit ham bo'sh bo'lsa, bot "
            "AI-siz (offline) generator bilan ishlaydi.")

    _h2(pdf, "3.8. Yangi admin qo'shish")
    _p(pdf, "'Adminlar' bo'limi orqali yangi admin qo'shish mumkin. Uch usul bor:")
    _bullets(pdf, [
        "ID orqali - foydalanuvchining Telegram raqamli ID sini kiritasiz.",
        "Username orqali - foydalanuvchi @username ini kiritasiz (foydalanuvchi kamida bir marta "
        "botni ishga tushirgan bo'lishi tavsiya etiladi).",
        "Telefon (kontakt) orqali - o'sha odamning kontaktini yuborasiz. Bot kontakt Telegram'da "
        "borligini tekshiradi: agar kontaktda foydalanuvchi ID si bo'lsa, u Telegram'da mavjud "
        "hisoblanadi va admin qilinadi. Aks holda topilmadi deb javob beradi.",
    ])
    _p(pdf, "Eslatma: Telegram maxfiylik qoidalari sababli oddiy telefon raqamini yozib qidirib "
            "bo'lmaydi - shuning uchun kontaktni ulashish talab qilinadi.")

    # ---- 4. Eslatmalar ----
    pdf.add_page()
    _h1(pdf, "4. Muhim eslatmalar")
    _bullets(pdf, [
        "Bot tokeni bir vaqtning o'zida faqat bitta joyda ishlashi kerak.",
        "Test faollashtirilmaguncha xodimlar uni topshira olmaydi.",
        "Xodim profilini haftada 1 martagina o'zgartira oladi.",
        "AI kalitlari to'g'ri kiritilgan bo'lsa, noto'g'ri javob variantlari sifatliroq bo'ladi.",
        "Savoli yo'q testni faollashtirib bo'lmaydi.",
        "O'chirilgan testni tiklab bo'lmaydi - ehtiyot bo'ling.",
    ])
    _p(pdf, "Savollar bo'lsa, tizim administratoriga murojaat qiling.")

    out = BytesIO(pdf.output())
    out.seek(0)
    return out
