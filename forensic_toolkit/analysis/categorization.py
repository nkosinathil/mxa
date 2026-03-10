"""
Message categorisation based on keywords.
"""
def categorize_message(msg: str) -> str:
    m = (msg or "").lower()
    cats = {
        'Personal / Conversational': ['hello', 'hi ', ' how are you', 'thanks', 'please', ' sorry', ' love ', 'family', 'good morning', 'good night'],
        'Banking & Finance': ['nedbank', 'capitec', 'fnb', 'standard bank', 'absa', 'sanlam', 'payment', 'transfer', 'account', 'balance', 'deposit', 'withdrawal', 'transaction'],
        'Utility / Work-Order': ['electricity', 'water', 'bill', 'service', 'repair', 'maintenance', 'invoice', 'eskom', 'municipal', 'work order', 'w/o'],
        'Promotional / Retail Marketing': ['sale', 'discount', 'offer', 'promo', 'deal', 'buy', 'shop', 'store', 'price', 'special', 'voucher', 'coupon', 'free'],
        'Wallet / Mobile Money': ['airtime', 'data', 'recharge', 'voucher', 'wallet', 'mobile money', 'mtn', 'vodacom', 'cell c', 'telkom', 'prepaid'],
    }
    for k, kws in cats.items():
        if any(kw in m for kw in kws):
            return k
    return 'Other / Unclassified'
