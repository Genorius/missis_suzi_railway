# Заглушка для хранения авторизации
user_auth = {}

def save_user_auth(user_id, order_id):
    user_auth[user_id] = order_id

def get_order_id_by_user_id(user_id):
    return user_auth.get(user_id)
