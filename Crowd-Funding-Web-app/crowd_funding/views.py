from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework import generics, status, views, viewsets, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from .models import User, EmailActivation, PasswordReset, Projects, Comment, Rating, Report, Donation, ExtraInfo
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ProjectSerializer, ProjectImagesSerializer, CommentSerializer,
    RatingSerializer, ReportSerializer, DonationSerializer,
    ExtraInfoSerializer, UpdateUserProfileSerializer
)
import uuid

# Register user and send activation email
class UserRegistrationView(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        activation = EmailActivation.objects.create(user=user)
        activation_link = f"http://localhost:8000/api/activate/{activation.activation_key}/"
        print(f"Sending activation email to: {user.email}")
        send_mail(
            subject="Activate your account",
            message=f"Click the link to activate your account: {activation_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

# Account activation
class ActivateAccountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, activation_key):
        try:
            activation = EmailActivation.objects.get(activation_key=activation_key)
            if activation.is_expired():
                return redirect("http://localhost:5173/activation-expired")
            activation.user.is_active = True
            activation.user.save()
            activation.delete()
            return redirect("http://localhost:5173/activation-success")
        except EmailActivation.DoesNotExist:
            return redirect("http://localhost:5173/invalid-activation")

# Login
class UserLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            "message": "Login successful.",
            "token": token.key,
            "user": UserProfileSerializer(user).data
        })

# Request password reset
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.get(email=email)
        reset = PasswordReset.objects.create(user=user)
        reset_link = f"http://localhost:8000/api/reset-password/{reset.reset_key}/"
        send_mail(
            subject="Password Reset Request",
            message=f"Click the link to reset your password: {reset_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
        return Response({"message": "Password reset email sent."})

# Confirm password reset
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, reset_key):
        try:
            reset = PasswordReset.objects.get(reset_key=reset_key, used=False)
            if reset.is_expired():
                return Response({"error": "Reset link expired."}, status=status.HTTP_400_BAD_REQUEST)
        except PasswordReset.DoesNotExist:
            return Response({"error": "Invalid reset key."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset.user.set_password(serializer.validated_data['new_password'])
        reset.user.save()
        reset.used = True
        reset.save()
        return Response({"message": "Password reset successful."})

# Get user profile
class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

# Logout
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)

# Check Auth
class CheckAuthView(APIView):
    def get(self, request):
        if request.user.is_authenticated:
            return Response({'is_authenticated': True, 'email': request.user.email})
        return Response({'is_authenticated': False})

# Project ViewSet
class ProjectView(viewsets.ModelViewSet):
    queryset = Projects.objects.prefetch_related("tags", "images").all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        serializer.save(uid=self.request.user)

    def update(self, request, *args, **kwargs):
        project = self.get_object()
        serializer = self.get_serializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if 'tags' in request.data:
            project.tags.set(request.data['tags'])

    @action(detail=True, methods=['POST'], url_path='add-image')
    def add_image(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectImagesSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project=project)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Project Detail
class ProjectDetailView(generics.RetrieveAPIView):
    queryset = Projects.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# Similar Projects
class SimilarProjectsView(APIView):
    def get(self, request, pk):
        try:
            project = Projects.objects.get(pk=pk)
            tags = project.tags.all()
            similar_projects = Projects.objects.filter(tags__in=tags).exclude(pk=pk).distinct()[:4]
            serializer = ProjectSerializer(similar_projects, many=True, context={'request': request})
            return Response(serializer.data)
        except Projects.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

# Create Comment
class CommentCreateView(generics.CreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        project_id = self.request.data.get('project_id')
        parent_id = self.request.data.get('parent_id')
        serializer.save(
            user=self.request.user,
            project=Projects.objects.get(pk=project_id),
            parent=Comment.objects.get(pk=parent_id) if parent_id else None
        )

# Create Rating
class RatingCreateView(generics.CreateAPIView):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        project_id = self.request.data.get('project_id')
        serializer.save(user=self.request.user, project=Projects.objects.get(pk=project_id))

# Create Report
class ReportCreateView(generics.CreateAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        project_id = self.request.data.get('project_id')
        comment_id = self.request.data.get('comment_id')
        serializer.save(
            user=self.request.user,
            project=Projects.objects.get(pk=project_id) if project_id else None,
            comment=Comment.objects.get(pk=comment_id) if comment_id else None
        )

# Create Donation
class DonationCreateView(generics.CreateAPIView):
    queryset = Donation.objects.all()
    serializer_class = DonationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        project_id = self.request.data.get('project_id')
        serializer.save(user=self.request.user, project=Projects.objects.get(pk=project_id))

# Cancel Project
class CancelProjectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            project = Projects.objects.get(pk=pk, uid=request.user)
            if project.can_cancel():
                project.delete()
                return Response({"message": "Project cancelled successfully"})
            return Response({"error": "Cannot cancel project"}, status=status.HTTP_400_BAD_REQUEST)
        except Projects.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

# Render project template
def project_detail_template(request, pk):
    project = get_object_or_404(Projects, pk=pk)
    tags = project.tags.all()
    similar_projects = Projects.objects.filter(tags__in=tags).exclude(pk=pk).distinct()[:4]
    return render(request, 'projects.html', {
        'project': project,
        'similar_projects': similar_projects
    })

# Extra user info view
class ExtraInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        extra_info, _ = ExtraInfo.objects.get_or_create(user=request.user)
        serializer = ExtraInfoSerializer(extra_info)
        return Response(serializer.data)

    def post(self, request):
        extra_info, _ = ExtraInfo.objects.get_or_create(user=request.user)
        serializer = ExtraInfoSerializer(extra_info, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Delete user account
class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        password = request.data.get('password')
        if not password:
            return Response({'error': 'Password is required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        if not user.check_password(password):
            return Response({'error': 'Incorrect password.'}, status=status.HTTP_400_BAD_REQUEST)

        user.delete()
        return Response({'message': 'Account deleted successfully.'}, status=status.HTTP_200_OK)

# Update user profile
class UpdateUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UpdateUserProfileSerializer(
            request.user, data=request.data, partial=True, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Profile updated successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
