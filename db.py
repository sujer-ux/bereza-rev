from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def find_seller_by_username(username: str):
    """Найти продавца по username (без @)"""
    # Убираем @ если пользователь ввел с ним
    username = username.lstrip('@').lower()
    
    result = supabase.table('sellers')\
        .select('*')\
        .eq('username', username)\
        .execute()
    
    if result.data:
        return result.data[0]
    return None

def get_seller_reviews(seller_id: int):
    """Получить все отзывы продавца"""
    result = supabase.table('reviews')\
        .select('*')\
        .eq('seller_id', seller_id)\
        .order('created_at', desc=True)\
        .execute()
    
    return result.data

def add_review(seller_id: int, rating: int, comment: str, reviewer_name: str, image_url: str = None):
    """Добавить новый отзыв"""
    data = {
        'seller_id': seller_id,
        'rating': rating,
        'comment': comment,
        'reviewer_name': reviewer_name,
        'image_url': image_url
    }
    
    result = supabase.table('reviews').insert(data).execute()
    return result.data[0] if result.data else None

def get_seller_avg_rating(seller_id: int):
    """Получить средний рейтинг продавца"""
    reviews = get_seller_reviews(seller_id)
    if not reviews:
        return 0, 0
    
    total = sum(r['rating'] for r in reviews)
    avg = total / len(reviews)
    return round(avg, 1), len(reviews)