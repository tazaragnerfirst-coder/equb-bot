# ══════════════════════════════════════════
# translations.py
# ሁሉም የተጠቃሚ-ተኮር ጽሁፍ (button ስሞች፣ መልክቶች) እዚህ ብቻ ይቀየራሉ።
# ⚠️ አንድ button ጽሁፍ ስትቀይር button_matchers.py ውስጥ ምንም መንካት አያስፈልግም -
#    ምክንያቱም እነዚያ ሊስቶች ከዚህ T dictionary በራሳቸው ይመነጫሉ (derive ያደርጋሉ)።
# ══════════════════════════════════════════
from config_extra import BRAND_SIGNATURE

T = {
    "am": {
        "pick_btn":       "❇️ ቁጥር ምረጥ ❇️",
        "my_tickets_btn": "✴️ የኔ ትኬቶች ✴️",
        "info_btn":       "ℹ️ አጠቃቀም ",
        "admin_btn":      "🔰 ADMIN 🔰",
        "admin_cards_btn":"📋 CARDS",
        "home_btn":       "🔝 ዋና ገጽ",
        "cancel_btn":     "❌ ሰርዝ",
        "back_btn":       "🔙 ተመለስ",

        "join_required": (
            "⚠️ *ቦቱን ለመጠቀም መጀመሪያ*\n"
            "*ቡድናችንን መቀላቀል ይኖርብዎታል!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 ቀላቅለው ✅ ተቀላቅያለሁ ይጫኑ።"
        ),
        "join_btn":       "📢 ቡድኑን ቀላቀሉ",
        "joined_btn":     "✅ ተቀላቅያለሁ",
        "not_joined":     "⚠️ ገና ቡድኑን አልተቀላቀሉም። ቀላቅለው እንደገና ይሞክሩ።",

        "contact_required": (
            "📱 *ቦቱን ለመጠቀም ስልክ ቁጥርዎን ማጋራት ያስፈልጋል*\n"
            "━━━━━━━━━━━━━━━\n"
            "ይህ የሚያስፈልገው ክፍያ ሲፈጽሙ በራስ-ሰር\n"
            "መረጃዎን ለመሙላት ነው።\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 ከስር ያለውን ቁልፍ ተጭነው ኮንታክትዎን ያጋሩ።"
        ),
        "contact_btn":    "📱 ኮንታክት አጋራ",
        "contact_own_only": "⚠️ እባክዎ የራስዎን ኮንታክት ብቻ ያጋሩ።",

        "home_text": (
            "🎉 *{title}*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ አንደኛ እጣ 👉 {prize1}\n"
            "2️⃣ ሁለተኛ እጣ 👉 {prize2}\n"
            "3️⃣ ሦስተኛ እጣ 👉 {prize3}\n"
            "━━━━━━━━━━━━━━━\n"
            "የትኬት ብዛት = {total}\n"
            "የአንዱ ትኬት ዋጋ = {price}\n"
            "━━━━━━━━━━━━━━━\n"
            "የሚፈልጉትን ትኬት ቁጥር ለመምረጥ\n"
            "ከስር ያለውን 👇 \" ❇️ ቁጥር ምረጥ ❇️ \"\n"
            "የሚለውን ቁልፍ ይጫኑ!"
        ),

        "payment_intro": (
            "💳 *ክፍያ*\n"
            "━━━━━━━━━━━━━━━\n"
            "አሁን የመረጧቸው ቁጥሮች 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "የትኬት ብዛት = {count}\n"
            "ዋጋ = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "ክፍያ ለመፈጸም ከስር ያለውን 👇\n"
            "\"💳 ክፍያ ቀጥል\" የሚለውን ይጫኑ!"
        ),
        "pay_cbe_btn":     "🏦 CBE",
        "pay_telebirr_btn":"📱 TELE BIRR",
        "pay_back_btn":    "🔙 ተመለስ",

        "cbe_msg": (
            "🏦 *CBE*\n"
            "━━━━━━━━━━━━━━━\n"
            "አካዉንት ቁጥር 👉 `{account}`\n"
            "ስም 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "ድምር ዋጋ = {total} ብር\n"
            "━━━━━━━━━━━━━━━\n"
            "ክፍያ ከፈፀሙ በኋላ\n"
            "የከፈሉበትን ደረሰኝ (screenshot)\n"
            "ይላኩልን 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "telebirr_msg": (
            "📱 *TELE BIRR*\n"
            "━━━━━━━━━━━━━━━\n"
            "አካዉንት ቁጥር 👉 `{account}`\n"
            "ስም 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "ድምር ዋጋ = {total} ብር\n"
            "━━━━━━━━━━━━━━━\n"
            "ክፍያ ከፈፀሙ በኋላ\n"
            "የከፈሉበትን ደረሰኝ (screenshot)\n"
            "ይላኩልን 👇🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "ask_name":      "👤 *ሙሉ ስምዎን ይፃፉ:*\nምሳሌ: አበበ ባልቻ",
        "ask_phone":     "📞 *ስልክ ቁጥርዎን ይፃፉ:*\nምሳሌ: 09########",
        "invalid_phone": "⚠️ ትክክለኛ ስልክ ቁጥር ይፃፉ። ምሳሌ: 0911223344",
        "receipt_only":  "⚠️ እባክዎ *screenshot (ፎቶ)* ይላኩ።",

        "preview_msg": (
            "📋 *ማረጋገጫ*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 ቁጥሮች: {nums}\n"
            "👤 ስም: {name}\n"
            "📞 ስልክ: {phone}\n"
            "💰 ዋጋ: {total} ብር\n"
            "💳 ዘዴ: {method}\n"
            "━━━━━━━━━━━━━━━"
        ),
        "confirm_send": "✅ ልክ ነው፣ ላክ",

        "sent_ok": (
            "✅ *ደረሰኝዎ ተልኳል!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👤 ስም: {name}\n"
            "📞 ስልክ: {phone}\n"
            "🎟 የመረጡት ቁጥር: {nums}\n"
            "💰 ድምር: {total} ብር\n"
            "💳 ዘዴ: {method}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ አድሚን ሲያረጋግጥ notification\n"
            "ይደርስዎታል። እናመሰግናለን!\n"
            "{brand}"
        ),

        "approved": (
            "🎉 *ክፍያዎ ተረጋግጧል!*\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ ክፍያዎ ተረጋግጧል!\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 ቁጥሮቾ: {nums}\n"
            "💰 {total} ብር\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ ቁጥሮቹ የእርስዎ ሆነዋል።\n"
            "እጣ እስኪቆረጥ ድረስ ይጠብቁ!\n"
            "✳️ እናመሰግናለን! ✳️\n"
            "{brand}"
        ),
        "rejected": (
            "❌ *ክፍያዎ አልተረጋገጠም።*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 ቁጥሮች: {nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "እባክዎ ትክክለኛ ማስረጃ ይላኩ\n"
            "ወይም ድጋሚ ይሞክሩ።"
        ),

        "my_tickets_hdr": "✴️ *የኔ ትኬቶች* ✴️",
        "my_tickets_body": (
            "ዉድ {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "አስካሁን የእርስዎ የሆኑት ቁጥሮች 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "የትኬት ብዛት = {count}\n"
            "ዋጋ = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "የእጣ መቁረጫ ቀን እስከሚደርስ\n"
            "ተጨማሪ ትኬቶችን መቁረጥ ይችላሉ።\n"
            "━━━━━━━━━━━━━━━\n"
            "✳️ እናመሰግናለን! ✳️"
        ),
        "my_tickets_pending": (
            "ዉድ {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ በሂደት ላይ ያሉ ቁጥሮች 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "የትኬት ብዛት = {count}\n"
            "ዋጋ = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ አድሚን እስኪያረጋግጥ ይጠብቁ።"
        ),
        "no_tickets": (
            "✴️ *የኔ ትኬቶች* ✴️\n"
            "━━━━━━━━━━━━━━━\n"
            "ምንም ትኬት የለዎትም።"
        ),
        "referral_btn": "👥 Referral",
        "back_home_btn": "🔙 Back",

        "referral_info": (
            "👥 *Referral ስርዓት*\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 የእርስዎ Referral ሊንክ:\n"
            "`{link}`\n"
            "━━━━━━━━━━━━━━━\n"
            "👥 የጋበዟቸው: *{count}* ሰዎች\n"
            "💰 ሊያገኙ የሚችሉ: *{reward}* ብር\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 ለእያንዳንዱ የሚጋብዟቸው ሰው\n"
            "በአንድ ሰው *2 ብር* ይከፈልዎታል!"
        ),

        "info_text": (
            "ℹ️ *ሙሉ አጠቃቀም መመሪያ*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ ቋንቋ ይምረጡ\n"
            "2️⃣ ቡድናችንን (እና ካለ ቻናላችንን) ይቀላቀሉ፣ ከዛ ✅ ተቀላቅያለሁ ይጫኑ\n"
            "3️⃣ ስልክ ቁጥርዎን ያጋሩ — ይህ በክፍያ ወቅት መረጃዎን በራስ-ሰር ለመሙላት ያገለግላል\n"
            "4️⃣ \"❇️ ቁጥር ምረጥ ❇️\" ተጭነው የሚፈልጉትን የትኬት ቁጥር(ሮች) ይምረጡ\n"
            "5️⃣ \"💳 ክፍያ ቀጥል\" ተጭነው CBE ወይም Telebirr ይምረጡ፣ ስምና ስልክ ያረጋግጡ፣ ከዛ የከፈሉበትን ደረሰኝ (screenshot) ይላኩ\n"
            "6️⃣ አድሚን ደረሰኙን ካረጋገጠ በኋላ ቁጥሮቹ የእርስዎ ይሆናሉ — የማረጋገጫ መልክት ይደርስዎታል\n"
            "7️⃣ በ\"✴️ የኔ ትኬቶች ✴️\" ማንኛውም ጊዜ የገዙትን/በሂደት ላይ ያሉትን ቁጥሮች ማየት ይችላሉ\n"
            "8️⃣ ጓደኞችዎን በ Referral ሊንክ ጋብዘው ለእያንዳንዱ የተጋበዘ ሰው 2 ብር ያግኙ\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *ማሳሰቢያ:* ትክክለኛ ደረሰኝ ብቻ ተቀባይነት ይኖረዋል፤ የተቀየረ ወይም ትርጉም የሌለው ደረሰኝ ውድቅ ይሆናል።\n"
            "📌 እርዳታ ካስፈለገዎት \"💬 Support\" ይጫኑ"
        ),

        "num_taken": "⚠️ ቁጥር {num} ቀድሞ ተይዟል! እንደገና ይምረጡ።",

        "sold_announce": "🎟 ቁጥር *{num}* ተሽጧል!",

        "skip_btn":       "⏭ Skip",
        "support_btn":    "💬 Support",
        "support_menu_text": (
            "🆘 *ሰፖርት*\n"
            "━━━━━━━━━━━━━━━\n"
            "እርዳታ ከፈለጉ ከስር ያሉትን ይምረጡ 👇"
        ),
        "feedback_btn":   "💬 አስተያየት መስጫ",
        "support_contact_btn": "📞 ሰፓርት መገናኛ",
        "feedback_prompt": "💬 *አስተያየትዎን ይፃፉ:*\nመልክትዎ በቀጥታ ለአድሚን ይላካል።",
        "feedback_sent":   "✅ አስተያየትዎ ተልኳል! እናመሰግናለን።",
        "visit_group_btn":   "👥 Visit Group",
        "visit_channel_btn": "📢 Visit Channel",
        "mainmenu_btn":      "🔝 Main Menu",
    },

    "en": {
        "pick_btn":       "❇️ Pick Numbers ❇️",
        "my_tickets_btn": "✴️ My Tickets ✴️",
        "info_btn":       "ℹ️ How to Use ",
        "admin_btn":      "🔰 ADMIN 🔰",
        "admin_cards_btn":"📋 CARDS",
        "home_btn":       "🔝 Home",
        "cancel_btn":     "❌ Cancel",
        "back_btn":       "🔙 Back",

        "join_required": (
            "⚠️ *You must join our group*\n"
            "*to use this bot!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 Join then tap ✅ I Joined."
        ),
        "join_btn":       "📢 Join Group",
        "joined_btn":     "✅ I Joined",
        "not_joined":     "⚠️ You haven't joined yet. Please join and try again.",

        "contact_required": (
            "📱 *You must share your contact to use this bot*\n"
            "━━━━━━━━━━━━━━━\n"
            "This is needed to auto-fill your details\n"
            "during payment.\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 Tap the button below to share your contact."
        ),
        "contact_btn":    "📱 Share Contact",
        "contact_own_only": "⚠️ Please share your own contact only.",

        "home_text": (
            "🎉 *{title}*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ First Prize 👉 {prize1}\n"
            "2️⃣ Second Prize 👉 {prize2}\n"
            "3️⃣ Third Prize 👉 {prize3}\n"
            "━━━━━━━━━━━━━━━\n"
            "Total Tickets = {total}\n"
            "Ticket Price = {price}\n"
            "━━━━━━━━━━━━━━━\n"
            "To pick your ticket number\n"
            "press the button below 👇\n"
            "\" ❇️ Pick Numbers ❇️ \""
        ),

        "payment_intro": (
            "💳 *Payment*\n"
            "━━━━━━━━━━━━━━━\n"
            "Your selected numbers 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Ticket Count = {count}\n"
            "Total = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "Tap \"💳 Continue to Payment\" below 👇"
        ),
        "pay_cbe_btn":      "🏦 CBE",
        "pay_telebirr_btn": "📱 TELE BIRR",
        "pay_back_btn":     "🔙 Back",

        "cbe_msg": (
            "🏦 *CBE*\n"
            "━━━━━━━━━━━━━━━\n"
            "Account Number 👉 `{account}`\n"
            "Name 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "Total Amount = {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Please pay using this account\n"
            "and send us your receipt\n"
            "(screenshot) 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "telebirr_msg": (
            "📱 *TELE BIRR*\n"
            "━━━━━━━━━━━━━━━\n"
            "Account Number 👉 `{account}`\n"
            "Name 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "Total Amount = {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Please pay using this account\n"
            "and send us your receipt\n"
            "(screenshot) 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "ask_name":      "👤 *Enter your full name:*\nExample: Abebe Kebede",
        "ask_phone":     "📞 *Enter your phone number:*\nExample: 09########",
        "invalid_phone": "⚠️ Please enter a valid phone number. Example: 0911223344",
        "receipt_only":  "⚠️ Please send a *screenshot (photo)*.",

        "preview_msg": (
            "📋 *Confirmation*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Numbers: {nums}\n"
            "👤 Name: {name}\n"
            "📞 Phone: {phone}\n"
            "💰 Total: {total} ETB\n"
            "💳 Method: {method}\n"
            "━━━━━━━━━━━━━━━"
        ),
        "confirm_send": "✅ Correct, Send",

        "sent_ok": (
            "✅ *Receipt sent!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👤 Name: {name}\n"
            "📞 Phone: {phone}\n"
            "🎟 Numbers: {nums}\n"
            "💰 Total: {total} ETB\n"
            "💳 Method: {method}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ You will be notified once\n"
            "admin confirms. Thank you!\n"
            "{brand}"
        ),

        "approved": (
            "🎉 *Payment Confirmed!*\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ Your payment is confirmed!\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Numbers: {nums}\n"
            "💰 {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Your numbers are reserved.\n"
            "Wait for the draw!\n"
            "✳️ Thank you! ✳️\n"
            "{brand}"
        ),
        "rejected": (
            "❌ *Payment Not Confirmed.*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Numbers: {nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Please send a valid receipt\n"
            "or try again."
        ),

        "my_tickets_hdr": "✴️ *My Tickets* ✴️",
        "my_tickets_body": (
            "Dear {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "Your reserved numbers 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Ticket Count = {count}\n"
            "Total = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "You can buy more tickets\n"
            "until the draw date.\n"
            "━━━━━━━━━━━━━━━\n"
            "✳️ Thank you! ✳️"
        ),
        "my_tickets_pending": (
            "Dear {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Pending numbers 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Ticket Count = {count}\n"
            "Total = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Waiting for admin approval."
        ),
        "no_tickets": (
            "✴️ *My Tickets* ✴️\n"
            "━━━━━━━━━━━━━━━\n"
            "You have no tickets yet."
        ),
        "referral_btn":  "👥 Referral",
        "back_home_btn": "🔙 Back",

        "referral_info": (
            "👥 *Referral System*\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 Your Referral Link:\n"
            "`{link}`\n"
            "━━━━━━━━━━━━━━━\n"
            "👥 Referred: *{count}* people\n"
            "💰 Reward: *{reward}* ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 Earn *2 ETB* for every\n"
            "person you invite, paid at draw!"
        ),

        "info_text": (
            "ℹ️ *Complete Guide*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ Choose your language\n"
            "2️⃣ Join our group (and channel, if shown), then tap ✅ I Joined\n"
            "3️⃣ Share your phone number — this auto-fills your info during payment\n"
            "4️⃣ Tap \"❇️ Pick Numbers ❇️\" and select the ticket number(s) you want\n"
            "5️⃣ Tap \"💳 Continue to Payment\", choose CBE or Telebirr, confirm your name & phone, then upload your payment receipt (screenshot)\n"
            "6️⃣ Once admin verifies your receipt, the numbers become yours — you'll get a confirmation message\n"
            "7️⃣ Check \"✴️ My Tickets ✴️\" anytime to see your purchased/pending numbers\n"
            "8️⃣ Invite friends with your Referral link and earn 2 ETB for each person you invite\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *Note:* Only valid receipts are accepted; edited or unclear receipts will be rejected.\n"
            "📌 Need help? Tap \"💬 Support\""
        ),

        "num_taken": "⚠️ Number {num} is already taken! Please pick again.",

        "sold_announce": "🎟 Number *{num}* sold!",

        "skip_btn":       "⏭ Skip",
        "support_btn":    "💬 Support",
        "support_menu_text": (
            "🆘 *Support*\n"
            "━━━━━━━━━━━━━━━\n"
            "Choose an option below 👇"
        ),
        "feedback_btn":   "💬 Send Feedback",
        "support_contact_btn": "📞 Contact Support",
        "feedback_prompt": "💬 *Type your feedback:*\nYour message will be sent directly to the admin.",
        "feedback_sent":   "✅ Your feedback has been sent! Thank you.",
        "visit_group_btn":   "👥 Visit Group",
        "visit_channel_btn": "📢 Visit Channel",
        "mainmenu_btn":      "🔝 Main Menu",
    },

    "or": {
        "pick_btn":       "❇️ Lakkoofsa Filadhu ❇️",
        "my_tickets_btn": "✴️ Tikeetii Koo ✴️",
        "info_btn":       "ℹ️ Akkamitti fayyadamuu ",
        "admin_btn":      "🔰 ADMIN 🔰",
        "admin_cards_btn":"📋 CARDS",
        "home_btn":       "🔝 Fuula Jalqabaa",
        "cancel_btn":     "❌ Haquu",
        "back_btn":       "🔙 Deebi'i",

        "join_required": (
            "⚠️ *Garee keenya makamuun*\n"
            "*bot kana fayyadamuuf barbaachisaadha!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 Makamtee booda ✅ Makamuun koo cuqaasi."
        ),
        "join_btn":       "📢 Garee Makamu",
        "joined_btn":     "✅ Makamuun koo",
        "not_joined":     "⚠️ Ammallee garee hin makaamin. Makamtee ammas yaali.",

        "contact_required": (
            "📱 *Bot kana fayyadamuuf lakkoofsa bilbilaa kee qooduu qabda*\n"
            "━━━━━━━━━━━━━━━\n"
            "Kun kaffaltii yeroo raawwattu odeeffannoo\n"
            "kee ofumaan guutuuf barbaachisa.\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 Mallattoo gadii tuqi kontaakticha qoodi."
        ),
        "contact_btn":    "📱 Kontaakti Qoodi",
        "contact_own_only": "⚠️ Maaloo kontaaktii kee qofa qoodi.",

        "home_text": (
            "🎉 *{title}*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ Badhaasa 1ffaa 👉 {prize1}\n"
            "2️⃣ Badhaasa 2ffaa 👉 {prize2}\n"
            "3️⃣ Badhaasa 3ffaa 👉 {prize3}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii = {total}\n"
            "Gatii tikeetii tokkoo = {price}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii filachuuf\n"
            "cuqaasi 👇 \" ❇️ Lakkoofsa Filadhu ❇️ \""
        ),

        "payment_intro": (
            "💳 *Kaffaltii*\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa filatame 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii = {count}\n"
            "Gatii = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "\"💳 Kaffaltiitti Itti Fufi\" jedhu cuqaasi 👇"
        ),
        "pay_cbe_btn":      "🏦 CBE",
        "pay_telebirr_btn": "📱 TELE BIRR",
        "pay_back_btn":     "🔝 Deebi'i",

        "cbe_msg": (
            "🏦 *CBE*\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa akkaawuntii 👉 `{account}`\n"
            "Maqaa 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "Gatii waliigalaa = {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Akkaawuntii kana fayyadamuun\n"
            "kaffalii, booda beeksisa\n"
            "(screenshot) ergi 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "telebirr_msg": (
            "📱 *TELE BIRR*\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa akkaawuntii 👉 `{account}`\n"
            "Maqaa 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "Gatii waliigalaa = {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Akkaawuntii kana fayyadamuun\n"
            "kaffalii, booda beeksisa\n"
            "(screenshot) ergi 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "ask_name":      "👤 *Maqaa guutuu kee barreessi:*\nFkn: Abebe Kebede",
        "ask_phone":     "📞 *Lakkoofsa bilbilaa kee barreessi:*\nFkn: 09########",
        "invalid_phone": "⚠️ Lakkoofsa bilbilaa sirrii barreessi. Fkn: 0911223344",
        "receipt_only":  "⚠️ *Screenshot (suuraa)* ergi.",

        "preview_msg": (
            "📋 *Mirkaneessaa*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Lakkoofsa: {nums}\n"
            "👤 Maqaa: {name}\n"
            "📞 Bilbila: {phone}\n"
            "💰 Gatii: {total} ETB\n"
            "💳 Mala: {method}\n"
            "━━━━━━━━━━━━━━━"
        ),
        "confirm_send": "✅ Sirriidha, Ergi",

        "sent_ok": (
            "✅ *Beeksisni ergame!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👤 Maqaa: {name}\n"
            "📞 Bilbila: {phone}\n"
            "🎟 Lakkoofsa: {nums}\n"
            "💰 Waliigala: {total} ETB\n"
            "💳 Mala: {method}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Admin mirkaneesu booda\n"
            "beeksifama. Galatoomi!\n"
            "{brand}"
        ),

        "approved": (
            "🎉 *Kaffaltiins mirkanaa'e!*\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ Kaffaltiin kee mirkanaa'e!\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Lakkoofsa: {nums}\n"
            "💰 {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsi kee qabame.\n"
            "Fiigichaa eegi!\n"
            "✳️ Galatoomi! ✳️\n"
            "{brand}"
        ),
        "rejected": (
            "❌ *Kaffaltiins hin mirkanaa'in.*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Lakkoofsa: {nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Beeksisa sirrii ergi\n"
            "ykn ammas yaali."
        ),

        "my_tickets_hdr": "✴️ *Tikeetii Koo* ✴️",
        "my_tickets_body": (
            "Kabajamaa {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa kee 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii = {count}\n"
            "Gatii = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "Guyyaa fiigichaa dura\n"
            "tikeetii dabalataa bitachuu dandeessa.\n"
            "━━━━━━━━━━━━━━━\n"
            "✳️ Galatoomi! ✳️"
        ),
        "my_tickets_pending": (
            "Kabajamaa {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Lakkoofsa eegaa jiru 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii = {count}\n"
            "Gatii = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Admin mirkaneessuu eegaa jira."
        ),
        "no_tickets": (
            "✴️ *Tikeetii Koo* ✴️\n"
            "━━━━━━━━━━━━━━━\n"
            "Tikeetii hin qabdu."
        ),
        "referral_btn":  "👥 Referral",
        "back_home_btn": "🔙 Back",

        "referral_info": (
            "👥 *Referral*\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 Link kee:\n"
            "`{link}`\n"
            "━━━━━━━━━━━━━━━\n"
            "👥 Affeerre: *{count}* namoota\n"
            "💰 Badhaasa: *{reward}* ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 Nama hunda affeerteef\n"
            "Nama tokkoof *2 ETB* argatta!"
        ),

        "info_text": (
            "ℹ️ *Qajeelfama Guutuu*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ Afaan filadhu\n"
            "2️⃣ Garee keenya (fi channel, yoo jiraate) makami, ergasii ✅ Makamuun koo tuqi\n"
            "3️⃣ Lakkoofsa bilbilaa kee qoodi — kun odeeffannoo kee kaffaltii keessatti ofumaan guutuuf gargaara\n"
            "4️⃣ \"❇️ Lakkoofsa Filadhu ❇️\" tuqiitii lakkoofsa tikeetii barbaaddu filadhu\n"
            "5️⃣ \"💳 Kaffaltiitti Itti Fufi\" tuqi, CBE ykn Telebirr filadhu, maqaa fi bilbila mirkaneessi, ergasii ragaa kaffaltii (screenshot) ergi\n"
            "6️⃣ Admin ragaa kee erga mirkaneessee booda lakkoofsi kee siif ta'a — ergaa mirkaneessaa siif erga\n"
            "7️⃣ Yeroo barbaaddetti \"✴️ Tikeetii Koo ✴️\" ilaaluun lakkoofsa bitatte/eegaa jiru argachuu dandeessa\n"
            "8️⃣ Hiriyoota kee link Referral kaatiin afeeruun nama afeerte hunda irraa 2 ETB argadha\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *Yaadadhu:* Ragaan sirrii qofa fudhatama; ragaan jijjiirame ykn ifa hin taane ni kufa.\n"
            "📌 Gargaarsa yoo barbaadde \"💬 Support\" tuqi"
        ),

        "num_taken": "⚠️ Lakkoofsi {num} fudhataame! Ammas filadhu.",

        "sold_announce": "🎟 Lakkoofsi *{num}* gurgurame!",

        "skip_btn":       "⏭ Skip",
        "support_btn":    "💬 Support",
        "support_menu_text": (
            "🆘 *Support*\n"
            "━━━━━━━━━━━━━━━\n"
            "Filannoo gadii filadhu 👇"
        ),
        "feedback_btn":   "💬 Yaada Ergi",
        "support_contact_btn": "📞 Kontaakti Sapoortii",
        "feedback_prompt": "💬 *Yaada kee barreessi:*\nErgaan kee kallattiin admin bira gaha.",
        "feedback_sent":   "✅ Yaadni kee ergameera! Galatoomi.",
        "visit_group_btn":   "👥 Visit Group",
        "visit_channel_btn": "📢 Visit Channel",
        "mainmenu_btn":      "🔝 Main Menu",
    }
}
