
import sys

from django.utils.timezone import now

try:
    from django.db import models
except Exception:
    print("There was an error loading Django modules. Do you have Django installed?")
    sys.exit()

from django.conf import settings


# Instructor model
class Instructor(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    full_time = models.BooleanField(default=True)
    total_learners = models.IntegerField()

    def __str__(self):
        return self.user.username


# Learner model
class Learner(models.Model):
    STUDENT = "student"
    DEVELOPER = "developer"
    DATA_SCIENTIST = "data_scientist"
    DATABASE_ADMIN = "dba"

    OCCUPATION_CHOICES = [
        (STUDENT, "Student"),
        (DEVELOPER, "Developer"),
        (DATA_SCIENTIST, "Data Scientist"),
        (DATABASE_ADMIN, "Database Admin"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    occupation = models.CharField(
        max_length=20,
        choices=OCCUPATION_CHOICES,
        default=STUDENT,
    )
    social_link = models.URLField(max_length=200)

    def __str__(self):
        return f"{self.user.username},{self.occupation}"


# Course model
class Course(models.Model):
    name = models.CharField(
        max_length=30,
        default="online course",
    )
    image = models.ImageField(upload_to="course_images/")
    description = models.CharField(max_length=1000)
    pub_date = models.DateField(null=True)
    instructors = models.ManyToManyField(Instructor)
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Enrollment",
    )
    total_enrollment = models.IntegerField(default=0)

    # Used by the course list view
    is_enrolled = False

    def __str__(self):
        return f"Name: {self.name},Description: {self.description}"


# Lesson model
class Lesson(models.Model):
    title = models.CharField(max_length=200, default="title")
    order = models.IntegerField(default=0)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
    )
    content = models.TextField()

    def __str__(self):
        return self.title


# Enrollment model
class Enrollment(models.Model):
    AUDIT = "audit"
    HONOR = "honor"
    BETA = "BETA"

    COURSE_MODES = [
        (AUDIT, "Audit"),
        (HONOR, "Honor"),
        (BETA, "BETA"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
    )
    date_enrolled = models.DateField(default=now)
    mode = models.CharField(
        max_length=5,
        choices=COURSE_MODES,
        default=AUDIT,
    )
    rating = models.FloatField(default=5.0)


# Question model
class Question(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
    )
    content = models.CharField(max_length=200)
    grade = models.IntegerField(default=0)

    def __str__(self):
        return self.content

    def is_get_score(self, selected_choice_ids):
        correct_choice_ids = set(
            self.choice_set.filter(is_correct=True).values_list("id", flat=True)
        )
        selected_choice_ids = set(selected_choice_ids)
        return self.grade if selected_choice_ids == correct_choice_ids else 0


# Choice model
class Choice(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
    )
    content = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.content


# Submission model
class Submission(models.Model):
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
    )
    choices = models.ManyToManyField(Choice)

    def __str__(self):
        return (
            f"Submission(id={self.id}, course={self.enrollment.course_id}, "
            f"user={self.enrollment.user_id})"
        )
