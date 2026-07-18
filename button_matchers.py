# ══════════════════════════════════════════
# button_matchers.py
# ⚠️ ይህ ፋይል በእጅ አይቀየርም! ሁሉም ሊስቶች ከ translations.py T dictionary
#    በራሳቸው ይመነጫሉ (derive ያደርጋሉ)። ስለዚህ button ጽሁፍ ስትቀይር
#    translations.py ውስጥ ብቻ ቀይረው፣ እዚህ ምንም መንካት አያስፈልግም።
# ══════════════════════════════════════════
from translations import T

LANGS = list(T.keys())  # ["am", "en", "or"]


def _collect(key):
    """T['am'][key], T['en'][key], T['or'][key] ሁሉንም በአንድ ሊስት ይመልሳል"""
    return [T[lang][key] for lang in LANGS if key in T[lang]]


# ── Reply-keyboard button matchers (any_message_home router uses these) ──
home_words     = _collect("home_btn") + ["🏠 Main Menu", "🔙 Back"]
cancel_words   = _collect("cancel_btn")
tickets_words  = _collect("my_tickets_btn")
admin_words    = _collect("admin_btn")
info_words     = _collect("info_btn")
pick_words     = _collect("pick_btn")
back_words     = _collect("back_btn")
support_words  = _collect("support_btn")
feedback_words = _collect("feedback_btn")
skip_words     = _collect("skip_btn")

# ── Note ──
# "home_words" ውስጥ "🏠 Main Menu" እና "🔙 Back" የሚል ተጨማሪ ጽሁፍ ኦርጅናሉ ኮድ ላይ
# hardcoded ሆኖ ተገኝቷል (mainmenu_btn / back_home_btn ቁልፎች ናቸው)።
# ወደፊት ካስፈለገ ይሄንንም ከ T["xx"]["mainmenu_btn"] እና T["xx"]["back_home_btn"]
# እንዲመነጭ ማድረግ ይቻላል — አሁን ግን ኦርጅናሉን ባህሪ ላለመቀየር እንደነበረው ተትቷል።
