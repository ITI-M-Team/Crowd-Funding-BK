from requests import Response
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.backends import ModelBackend

import project
from .models import *
import re

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password', 'confirm_password',
                  'mobile_phone', 'profile_picture']
        extra_kwargs={'password':{'write_only':True}}

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def validate_mobile_phone(self, value):
        pattern = r'^(\+20|0)?(10|11|12|15)\d{8}$'
        if not re.match(pattern, value):
            raise serializers.ValidationError("Invalid Egyptian phone number format")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password= validated_data.pop('password',None)
        user = User(**validated_data)
        if password:
            user.password=make_password(password)
        user.save()
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
       
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials.')
            if not user.is_active:
                raise serializers.ValidationError('Account not activated. Please check your email.')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include "email" and "password".')
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'mobile_phone', 'profile_picture']
        read_only_fields = ['id', 'email']

## category 
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model=Category
        fields=['id','name']
## Tags
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model=Tag
        fields=['id','name']
## Project Pictures
class ProjectImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model=ProjectImages
        fields=['id','image','uploaded_at']
## project serializer

class ProjectSerializer(serializers.ModelSerializer):
    # category = serializers.SlugRelatedField(
    #     slug_field='name',
    #     queryset=Category.objects.all()
    # )
    # tags = serializers.SlugRelatedField(
    #     many=True,
    #     slug_field='name',
    #     queryset=Tag.objects.all()
    # )
    category = serializers.CharField()  
    tags = TagSerializer(many=True, read_only=True) 
    images = ProjectImagesSerializer(many=True, read_only=True)

    class Meta:
        model = Projects
        fields = ['id', 'title', 'details', 'totalTarget', 'startTime', 'endTime', 'uid', 'category', 'tags', 'images']
        extra_kwargs = {
            'uid': {'read_only': True}
        }

    def create(self, validated_data):
        # Extract category and tags from the validated data
        category = validated_data.pop('category')
        # tags = validated_data.pop('tags')
        tags=self.initial_data.getlist('tags')
        category_obj, _ = Category.objects.get_or_create(name=category)
        # Create the project instance
        

        # Get or create each tag (handle SlugRelatedField 'name')
        new_tags = []
        for tag in tags:
            tag_obj, _ = Tag.objects.get_or_create(name=tag)
            new_tags.append(tag_obj)
        
        project = Projects.objects.create(category=category_obj, **validated_data)
        project.tags.set(new_tags)
        # Handle image uploads
        request = self.context.get('request')
        if request and hasattr(request, 'FILES'):
            images = request.FILES.getlist('images')
            for image in images:
                ProjectImages.objects.create(project=project, image=image)
        return project
    ##log errors
    def to_internal_value(self, data):
        print("Incoming data to ProjectSerializer:", data)
        return super().to_internal_value(data)
        

    ##################################
    # Project Details
class DonationSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)

    class Meta:
        model = Donation
        fields = ['id', 'project', 'user', 'amount', 'created_at']
        read_only_fields = ['user', 'created_at']

class CommentSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'project', 'user', 'content', 'created_at', 'parent', 'replies']
        read_only_fields = ['user', 'created_at']

    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True).data
        return []

class ReportSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    project = ProjectSerializer(read_only=True, allow_null=True)
    comment = CommentSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Report
        fields = ['id', 'report_type', 'project', 'comment', 'user', 'reason', 'created_at']
        read_only_fields = ['user', 'created_at']

class RatingSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)

    class Meta:
        model = Rating
        fields = ['id', 'project', 'user', 'score', 'created_at']
        read_only_fields = ['user', 'created_at']

    # newtags = []
    # for tag in tags:
    #     newtag,_=Tag.objects.get_or_create(name=tag)
    #     newtags.append(newtag)
    # project=Projects.objects.create(category=newcategory,**validated_data)
    # project.tags.set(newtags)
    def create(self, validated_data):
        request = self.context.get('request')
        project = validated_data.get('project')
        images = request.FILES.getlist('images')
        for image in images:
            ProjectImages.objects.create(project=project, image=image) 
        return project
## (add Project and list all projects)
class ExtraInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtraInfo
        fields = ['birthdate', 'facebook_account', 'country']

class UpdateUserProfileSerializer(serializers.ModelSerializer):
    new_password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
    current_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'mobile_phone', 'profile_picture',
                  'current_password', 'new_password', 'confirm_password']
        extra_kwargs = {
            'profile_picture': {'required': False}
        }

    def validate(self, data):
        user = self.context['request'].user
        if not user.check_password(data['current_password']):
            raise serializers.ValidationError({'current_password': 'Current password is incorrect'})

        if 'new_password' in data:
            if data.get('new_password') != data.get('confirm_password'):
                raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
            validate_password(data['new_password'])

        return data

    def update(self, instance, validated_data):
        validated_data.pop('current_password', None)
        new_password = validated_data.pop('new_password', None)
        validated_data.pop('confirm_password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if new_password:
            instance.set_password(new_password)

        instance.save()
        return instance

    def create(self,validated_data):
        ##get the incoming ctargory and tags from FR
        category = validated_data.pop('category')
        tags = validated_data.pop('tags')
        ## Use Get or create DRF BIN
        newcategory, _ = Category.objects.get_or_create(name=category['name'])
        ## Same as tags but it sore as list
        newtags = []
        for tag in tags:
            newtag,_=Tag.objects.get_or_create(name=tag['name'])
            newtags.append(newtag)
        project=Projects.objects.create(category=newcategory,**validated_data)
        project.tags.set(newtags)
        return project
    