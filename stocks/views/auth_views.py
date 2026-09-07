import logging
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import ProgrammingError, OperationalError
from rest_framework import views, status, permissions
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from stocks.models import UserProfile

logger = logging.getLogger("stocks")


def _ensure_db_tables():
    """Self-healing helper to automatically apply migrations if database tables are uninitialized."""
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False)
        logger.info("Auto-applied migrations successfully.")
    except Exception as e:
        logger.warning(f"Auto-migration failed: {e}")


class SignupView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        for attempt in range(2):
            try:
                username = str(request.data.get('username') or '').strip()
                password = str(request.data.get('password') or '').strip()
                email = str(request.data.get('email') or '').strip().lower()

                if not username or not password:
                    return Response(
                        {'error': 'Username and password are required.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if len(username) < 3:
                    return Response(
                        {'error': 'Username must be at least 3 characters.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if len(password) < 6:
                    return Response(
                        {'error': 'Password must be at least 6 characters.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if User.objects.filter(username__iexact=username).exists():
                    return Response(
                        {'error': 'Username is already taken. Please choose another.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if email and User.objects.filter(email__iexact=email).exists():
                    return Response(
                        {'error': 'An account with this email already exists.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                user = User.objects.create_user(username=username, password=password, email=email)
                profile, _ = UserProfile.objects.get_or_create(user=user)
                token, _ = Token.objects.get_or_create(user=user)

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
                }, status=status.HTTP_201_CREATED)
            except (ProgrammingError, OperationalError, Exception) as e:
                err_str = str(e).lower()
                if ('relation' in err_str or 'does not exist' in err_str or 'no such table' in err_str) and attempt == 0:
                    logger.info("Missing table detected. Running migrations...")
                    _ensure_db_tables()
                    continue
                logger.error(f"Signup error: {e}")
                return Response(
                    {'error': f'Registration failed: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )


class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        for attempt in range(2):
            try:
                username_or_email = str(request.data.get('username') or '').strip()
                password = str(request.data.get('password') or '').strip()

                if not username_or_email or not password:
                    return Response(
                        {'error': 'Please provide both username/email and password.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                user = None

                # 1. Direct authentication
                user = authenticate(username=username_or_email, password=password)

                # 2. Case-insensitive username match or email match fallback
                if not user:
                    matched_user = User.objects.filter(username__iexact=username_or_email).first()
                    if not matched_user:
                        matched_user = User.objects.filter(email__iexact=username_or_email.lower()).first()

                    if matched_user:
                        user = authenticate(username=matched_user.username, password=password)

                if not user:
                    return Response(
                        {'error': 'Invalid username/email or password.'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )

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
            except (ProgrammingError, OperationalError, Exception) as e:
                err_str = str(e).lower()
                if ('relation' in err_str or 'does not exist' in err_str or 'no such table' in err_str) and attempt == 0:
                    logger.info("Missing table detected in login. Running migrations...")
                    _ensure_db_tables()
                    continue
                logger.error(f"Login error: {e}")
                return Response(
                    {'error': f'Login failed: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )



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

        new_email = request.data.get('email')
        if new_email and new_email.strip():
            clean_email = new_email.strip().lower()
            if User.objects.filter(email__iexact=clean_email).exclude(id=user.id).exists():
                return Response({'error': 'Email is already in use by another account.'}, status=status.HTTP_400_BAD_REQUEST)
            user.email = clean_email
            user.save()

        profile.phone = request.data.get('phone', profile.phone)
        profile.gender = request.data.get('gender', profile.gender)

        dob = request.data.get('date_of_birth')
        if dob:
            profile.date_of_birth = dob

        profile.bio = request.data.get('bio', profile.bio)

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

