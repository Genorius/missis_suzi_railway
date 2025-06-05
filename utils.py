

def save_review_to_crm(order_id, review_text):
    url = f"{CRM_URL}/api/v5/orders/{order_id}/edit"
    headers = {"X-API-KEY": API_KEY}
    data = {
        "customFields": {
            "comments": review_text
        }
    }
    response = requests.post(url, json=data, headers=headers)
    print(f"📨 Отправка отзыва: {response.status_code} {response.text}")
    return response.ok
