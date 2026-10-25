
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User

from .models import Course, Enrollment, Question, Choice, Submission

logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('psw', '')
        first_name = request.POST.get('firstname', '')
        last_name = request.POST.get('lastname', '')

        if not username or not password:
            context['message'] = 'Username and password are required.'
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        if User.objects.filter(username=username).exists():
            context['message'] = 'User already exists.'
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            password=password
        )
        login(request, user)
        return redirect('onlinecourse:index')

    return redirect('onlinecourse:index')


def login_request(request):
    context = {}

    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('psw', '')
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')

        context['message'] = 'Invalid username or password.'

    return render(
        request,
        'onlinecourse/user_login_bootstrap.html',
        context
    )


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    if user.is_authenticated:
        return Enrollment.objects.filter(
            user=user,
            course=course
        ).exists()
    return False


class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            course.is_enrolled = check_if_enrolled(
                self.request.user,
                course
            )

        return courses



class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'
    context_object_name = 'course'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        context['course'].is_enrolled = check_if_enrolled(
            self.request.user,
            course
        )
        context['lessons'] = course.lesson_set.all().order_by('order')
        context['questions'] = course.question_set.all().prefetch_related(
            'choice_set'
        )
        return context



def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if user.is_authenticated and not check_if_enrolled(user, course):
        Enrollment.objects.create(
            user=user,
            course=course,
            mode='honor'
        )
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse('onlinecourse:course_details', args=(course.id,))
    )


def extract_answers(request):
    selected_ids = []

    for key, value in request.POST.items():
        if key.startswith('choice_'):
            try:
                selected_ids.append(int(value))
            except (TypeError, ValueError):
                continue

    return selected_ids


def get_score(course, selected_ids):
    """
    Return (earned_score, total_score) for a course and selected choices.
    Only choices belonging to questions in this course are considered.
    """
    questions = Question.objects.filter(course=course)
    earned_score = 0
    total_score = 0

    for question in questions:
        total_score += question.grade
        if question.is_get_score(selected_ids):
            earned_score += question.grade

    return earned_score, total_score


def submit(request, course_id):
    if request.method != 'POST':
        return redirect(
            'onlinecourse:course_details',
            pk=course_id
        )

    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(enrollment=enrollment)

    selected_ids = extract_answers(request)

    for choice_id in selected_ids:
        choice = Choice.objects.filter(
            pk=choice_id,
            question__course=course
        ).first()

        if choice is not None:
            submission.choices.add(choice)

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


def show_exam_result(request, course_id, submission_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__course=course
    )

    if submission.enrollment.user_id != request.user.id:
        return HttpResponseForbidden(
            'You are not allowed to view this exam result.'
        )

    selected_ids = list(
        submission.choices.values_list('id', flat=True)
    )

    earned_score, total_score = get_score(course, selected_ids)

    questions = Question.objects.filter(course=course).prefetch_related(
        'choice_set'
    )
    selected_choices = submission.choices.all()
    question_results = []

    for question in questions:
        selected_choice = selected_choices.filter(
            question=question
        ).first()

        is_correct = (
            selected_choice is not None
            and question.is_get_score(selected_ids)
        )

        question_results.append({
            'question': question,
            'choices': question.choice_set.all(),
            'selected_choice': selected_choice,
            'correct_choices': question.choice_set.filter(is_correct=True),
            'is_correct': is_correct,
            'marks': question.grade if is_correct else 0,
        })

    percentage = (
        round(earned_score * 100 / total_score)
        if total_score > 0
        else 0
    )

    context = {
        'course': course,
        'submission': submission,
        'question_results': question_results,
        'selected_ids': selected_ids,
        'grade': earned_score,
        'possible': total_score,
        'total_score': total_score,
        'percentage': percentage,
        'passed': percentage >= 80,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
