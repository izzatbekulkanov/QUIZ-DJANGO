from account.models import CustomUser

def create_users():
    for i in range(10):
        username = f'user{i}'
        email = f'user{i}@example.com'
        user = CustomUser.objects.create_user(username=username, email=email, password='password123')
        print(f'User created: {user.username}')