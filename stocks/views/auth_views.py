from django.contrib.auth.models import User
from rest_framework import views, status, permissions
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
import re
from stocks.models import UserProfile

class SignupView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email', '')

        if not username or not password:
            return Response({'error': 'Username and password required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if len(password) < 6:
            return Response({'error': 'Password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if email and User.objects.filter(email=email).exists():
            return Response({'error': 'Email already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            
        user = User.objects.create_user(username=username, password=password, email=email)
        profile = UserProfile.objects.create(user=user)
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'profile': {
                    'phone': profile.phone,
                    'gender': profile.gender,
                    'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
                    'bio': profile.bio,
                    'profile_pic_base64': profile.profile_pic_base64
                }
            }
        }, status=status.HTTP_201_CREATED)

class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.contrib.auth import authenticate
        username_or_email = request.data.get('username')
        password = request.data.get('password')
        
        # Check if the user is trying to log in with email
        if "@" in username_or_email:
            users = User.objects.filter(email=username_or_email)
            if users.exists():
                for u in users:
                    user = authenticate(username=u.username, password=password)
                    if user:
                        break
            else:
                # No user with this email, maybe the username itself contains @
                user = authenticate(username=username_or_email, password=password)
        else:
            # Regular username login
            user = authenticate(username=username_or_email, password=password)

        if not user:
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
            
        token, _ = Token.objects.get_or_create(user=user)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'profile': {
                    'phone': profile.phone,
                    'gender': profile.gender,
                    'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
                    'bio': profile.bio,
                    'profile_pic_base64': profile.profile_pic_base64
                }
            }
        })

class UserContextView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'profile': {
                    'phone': profile.phone,
                    'gender': profile.gender,
                    'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
                    'bio': profile.bio,
                    'profile_pic_base64': profile.profile_pic_base64
                }
            }
        })

class UserProfileView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return Response({
            'phone': profile.phone,
            'gender': profile.gender,
            'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            'bio': profile.bio,
            'profile_pic_base64': profile.profile_pic_base64
        })

    def put(self, request):
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        
        # Update User Model Fields (Email)
        new_email = request.data.get('email')
        if new_email:
            user.email = new_email
            user.save()

        # Update Profile Model Fields
        profile.phone = request.data.get('phone', profile.phone)
        profile.gender = request.data.get('gender', profile.gender)
        
        dob = request.data.get('date_of_birth')
        if dob:
            profile.date_of_birth = dob
            
        profile.bio = request.data.get('bio', profile.bio)
        
        # update base64 picture
        pic = request.data.get('profile_pic_base64')
        if pic is not None:
            profile.profile_pic_base64 = pic

        profile.save()

        return Response({
            'success': True,
            'user_email': user.email,
            'profile': {
                'phone': profile.phone,
                'gender': profile.gender,
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
                'bio': profile.bio,
                'profile_pic_base64': profile.profile_pic_base64
            }
        })
