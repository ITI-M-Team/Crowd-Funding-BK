from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import uuid
from django.utils import timezone
from datetime import timedelta
import re

def validate_egyptian_phone(phone):
    pattern = r'^(\+20|0)?(10|11|12|15)\d{8}$'
    if not re.match(pattern, phone):
        raise ValueError("Invalid Egyptian phone number format")

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    mobile_phone = models.CharField(max_length=15, validators=[validate_egyptian_phone])
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    is_active = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'mobile_phone']

    objects = CustomUserManager()

class EmailActivation(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    activation_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)

    def __str__(self):
        return f"Activation for {self.user.email}"

class PasswordReset(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reset_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=1)

    def __str__(self):
        return f"Password reset for {self.user.email}"

###Projects model 

## Category Model
class Category(models.Model):
    id=models.AutoField(primary_key=True)
    name=models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True) 
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  #



    def __str__(self):
        return self.name

### Tags Model 
class Tag(models.Model):
    id=models.AutoField(primary_key=True)
    name=models.CharField(max_length=30,unique=True)

    def __str__(self):
        return self.name


class Projects(models.Model):
    id=models.AutoField(primary_key=True)
    title=models.CharField(max_length=30)
    details=models.TextField()
    totalTarget=models.FloatField()
    startTime=models.DateTimeField()
    endTime=models.DateTimeField()
    uid=models.ForeignKey('User',on_delete=models.CASCADE) # naming creator would be better
    category=models.ForeignKey('Category',on_delete=models.SET_NULL,null=True)
    tags=models.ManyToManyField('Tag',blank=True)


##########################NOTE


    def can_cancel(self):
        total_donations = sum(donation.amount for donation in self.donations.all())
        return total_donations < (self.totalTarget * 0.25)



    def __str__(self):
        return self.title


    
## Projects Images 
class ProjectImages(models.Model):
    project=models.ForeignKey('Projects',related_name='images',on_delete=models.CASCADE)
    image = models.ImageField(upload_to='projects_Images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    #####################################

# Project Details 

class Donation(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='donations')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} donated {self.amount} to {self.project.title}"
    #######################################3
class Comment(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies') # الجزء دة عشان ال replay on comments  self relation

    def __str__(self):
        return f"Comment by {self.user.email} on {self.project.title}"
    #########################################3

class Report(models.Model):
    REPORT_TYPES = (
        ('PROJECT', 'Project'),
        ('COMMENT', 'Comment'),
    )
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report by {self.user.email} on {self.report_type}"
    
    ##############################33
class Rating(models.Model):
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1 to 5
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['project', 'user'] # عشان اليوزر مايقيمش نفس المشروع مرتين

    def __str__(self):
        return f"{self.user.email} rated {self.project.title} {self.score}"
    
       
class ExtraInfo(models.Model):
        user = models.OneToOneField(User, on_delete=models.CASCADE)  # One-to-One relationship
        birthdate = models.DateField(null=True, blank=True)
        facebook_account = models.URLField(max_length=255, null=True, blank=True)
        country = models.CharField(max_length=100, null=True, blank=True)

        def __str__(self):
            return f"Extra info for {self.user.email}"
