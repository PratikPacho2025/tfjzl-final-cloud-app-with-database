
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User

from .models import Choice, Course, Enrollment, Question, Submission

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
    selected_ids = set()

    for key, value in request.POST.items():
        if key.startswith('choice_'):
            try:
                selected_ids.add(int(value))
            except (TypeError, ValueError):
                continue
            continue

        if key.startswith('choice'):
            raw_choice_id = key.replace('choice', '', 1)
            if raw_choice_id.isdigit():
                selected_ids.add(int(raw_choice_id))

    return selected_ids


def get_score(course, selected_ids):
    questions = Question.objects.filter(course=course).prefetch_related('choice_set')
    selected_choices = Choice.objects.filter(
        id__in=selected_ids,
        question__course=course,
    )
    selected_by_question = {}

    for choice in selected_choices:
        selected_by_question.setdefault(choice.question_id, set()).add(choice.id)

    earned_score = 0
    total_score = 0

    for question in questions:
        total_score += question.grade
        earned_score += question.is_get_score(
            selected_by_question.get(question.id, set())
        )

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

    selected_ids = extract_answers(request)
    valid_choices = Choice.objects.filter(
        id__in=selected_ids,
        question__course=course
    )

    submission = Submission.objects.create(enrollment=enrollment)
    submission.choices.set(valid_choices)

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

    selected_choices = submission.choices.filter(
        question__course=course
    ).select_related('question')
    selected_ids = list(selected_choices.values_list('id', flat=True))

    earned_score, total_score = get_score(course, selected_ids)

    questions = Question.objects.filter(course=course).prefetch_related('choice_set')
    selected_by_question = {}
    for choice in selected_choices:
        selected_by_question.setdefault(choice.question_id, []).append(choice)

    question_results = []

    for question in questions:
        selected_for_question = selected_by_question.get(question.id, [])
        selected_ids_for_question = {
            choice.id for choice in selected_for_question
        }
        correct_choices = list(
            question.choice_set.filter(is_correct=True)
        )
        is_correct = (
            question.is_get_score(selected_ids_for_question) == question.grade
        )

        question_results.append({
            'question': question,
            'selected_choices': selected_for_question,
            'selected_choice': selected_for_question[0] if selected_for_question else None,
            'correct_choices': correct_choices,
            'is_correct': is_correct,
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
