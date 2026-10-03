"""Authority-aware ground truth layered on top of canonical-50 v1."""
from __future__ import annotations

import re
from typing import Any, Mapping

EXPECTATIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "פרשנות תכליתית של חוזה לפי הלכת אפרופים": {"domains": ("contracts",), "authorities": ("אפרופים",)},
    "חובת תום לב במשא ומתן לקראת חוזה": {"domains": ("contracts",), "authorities": ("חוק החוזים חלק כללי",)},
    "פיצויים מוסכמים שאינם פרופורציונליים לנזק": {"domains": ("contracts",), "authorities": ("חוק החוזים תרופות",)},
    "תרופות בשל הפרת חוזה": {"domains": ("contracts",), "authorities": ("חוק החוזים תרופות",)},
    "אכיפת חוזה לפי החוק": {"domains": ("contracts",), "authorities": ("חוק החוזים תרופות",)},
    "אחריות מעוולים יחד לנזיקין": {"domains": ("torts",)},
    "מבחן הצפיות בעבירה של רשלנות": {"domains": ("torts",)},
    "פיצוי על נזק לא ממוני בנזיקין": {"domains": ("torts",)},
    "פיצויי פיטורים לעובד שפוטר ללא שימוע": {"domains": ("labor",), "authorities": ("חוק פיצויי פיטורים",)},
    "זכויות עובד בעת מחלה לפי חוק דמי מחלה": {"domains": ("labor",), "authorities": ("חוק דמי מחלה",)},
    "שעות עבודה ומנוחה לפי החוק": {"domains": ("labor",), "authorities": ("חוק שעות עבודה ומנוחה",)},
    "שוויון הזדמנויות בעבודה והפליה": {"domains": ("labor",), "authorities": ("חוק שוויון ההזדמנויות בעבודה",)},
    "זכויות חולה לקבלת מידע רפואי": {"authorities": ("חוק זכויות החולה",)},
    "ביטוח בריאות ממלכתי וזכאות": {"authorities": ("חוק ביטוח בריאות ממלכתי",)},
    "ילד נכה ביטוח לאומי קצבה": {"authorities": ("חוק הביטוח הלאומי",)},
    "סיכול חוזה לאור נסיבות בלתי צפויות": {"domains": ("contracts",), "authorities": ("חוק החוזים תרופות",)},
    "טעות בכריתת חוזה ועילת ביטול": {"domains": ("contracts",), "authorities": ("חוק החוזים חלק כללי",)},
    "הטעייה בעת כריתת חוזה": {"domains": ("contracts",), "authorities": ("חוק החוזים חלק כללי",)},
    "כפייה והשפעה בלתי הוגנת בכריתת חוזה": {"domains": ("contracts",), "authorities": ("חוק החוזים חלק כללי",)},
    "תניה מקפחת בחוזה אחיד": {"domains": ("contracts",), "authorities": ("חוק החוזים האחידים",)},
    "ויתור על זכויות חוזיות": {"domains": ("contracts",)},
    "עשיית עושר ולא במשפט": {"domains": ("contracts",), "authorities": ("חוק עשיית עושר ולא במשפט",)},
    "חוזה למראית עין": {"domains": ("contracts",), "authorities": ("חוק החוזים חלק כללי",)},
    "ערבות לחיוב חוזי": {"domains": ("contracts",), "authorities": ("חוק הערבות",)},
    "אחריות מחזיק במקרקעין כלפי מבקרים": {"domains": ("torts",)},
    "גרימת מטרד לשכן": {"domains": ("torts",)},
    "חובת הקטנת הנזק על הניזוק": {"domains": ("torts",)},
    "נטל הראיה בתביעת רשלנות": {"domains": ("torts", "evidence")},
    "רשלנות רפואית של רופא מטפל": {"domains": ("torts",)},
    "פגיעה בפרטיות בעידן הדיגיטלי": {"domains": ("torts", "constitutional"), "authorities": ("חוק הגנת הפרטיות",)},
    "אחריות יצרן למוצר פגום": {"domains": ("torts",), "authorities": ("חוק האחריות למוצרים פגומים",)},
    "רישיון מרצון בעוולת הסגת גבול": {"domains": ("torts",)},
    "עוולת תרמית בנזיקין": {"domains": ("torts",)},
    "תשלום שעות נוספות לעובד": {"domains": ("labor",), "authorities": ("חוק שעות עבודה ומנוחה",)},
    "שכר מינימום לעובד יומי": {"domains": ("labor",), "authorities": ("חוק שכר מינימום",)},
    "דמי הבראה לעובד שנתי": {"domains": ("labor",)},
    "תחולת הסכם קיבוצי כללי": {"domains": ("labor",), "authorities": ("חוק הסכמים קיבוציים",)},
    "הטרדה מינית במקום העבודה": {"domains": ("labor",), "authorities": ("חוק למניעת הטרדה מינית",)},
    "הודעה מוקדמת בעת פיטורים": {"domains": ("labor",), "authorities": ("חוק הודעה מוקדמת לפיטורים ולהתפטרות",)},
    "התפטרות בדין מפוטר": {"domains": ("labor",), "authorities": ("חוק פיצויי פיטורים",)},
    "הפליה בעבודה על רקע מין או גיל": {"domains": ("labor",), "authorities": ("חוק שוויון ההזדמנויות בעבודה",)},
    "מינוי אפוטרופוס על קטין": {"domains": ("family",), "authorities": ("חוק הכשרות המשפטית והאפוטרופסות",)},
    "הסכמה מדעת לטיפול רפואי": {"authorities": ("חוק זכויות החולה",)},
    "סודיות רפואית וזכות לעיין בתיק": {"authorities": ("חוק זכויות החולה",)},
    "סל שירותי הבריאות הממלכתי": {"authorities": ("חוק ביטוח בריאות ממלכתי",)},
}

_PUNCT = re.compile(r"[\[\]{}()\"׳״'.,:;–—-]+")

def normalize(value: str) -> str:
    return " ".join(_PUNCT.sub(" ", value or "").lower().split())

def validate(question: str, domain: str | None, bundle: Mapping[str, Any]) -> dict[str, Any]:
    exp = EXPECTATIONS.get(question, {})
    domains = tuple(exp.get("domains") or ())
    authorities = tuple(exp.get("authorities") or ())
    authority_text = " ".join([
        str(bundle.get("anchor_label") or ""),
        str(bundle.get("cluster_label") or ""),
        " ".join(str(x) for x in (bundle.get("statute_refs") or [])),
        str(bundle.get("anchor_quote") or "")[:1600],
    ])
    hay = normalize(authority_text)
    authority_ok = not authorities or any(normalize(a) in hay for a in authorities)
    # A precise primary authority is stronger than a missing classifier tag.
    # A conflicting non-empty domain still fails closed.
    domain_ok = (
        not domains
        or (domain or "") in domains
        or (not domain and bool(authorities) and authority_ok)
    )
    return {
        "expected_domains": list(domains),
        "expected_authorities": list(authorities),
        "strict_domain_ok": domain_ok,
        "strict_authority_ok": authority_ok,
    }
