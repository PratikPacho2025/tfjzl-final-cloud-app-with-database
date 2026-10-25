from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.http import HttpResponseRedirect
from .models import Course, Lesson, Enrollment, Question, Choice, Submission


def course_details(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    return render(request, 'onlinecourse/course_details_bootstrap.html', {'course': course})


def submit(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if request.method == 'POST':
        enrollment = Enrollment.objects.get(user=request.user, course=course)
        submission = Submission.objects.create(enrollment=enrollment)
        
        choice_ids = request.POST.getlist('choice')
        for choice_id in choice_ids:
            choice = Choice.objects.get(pk=choice_id)
            submission.choices.add(choice)
            
        return HttpResponseRedirect(reverse('onlinecourse:show_exam_result', args=(course.id, submission.id)))
    
    return HttpResponseRedirect(reverse('onlinecourse:course_details', args=(course.id,)))


def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)
    
    score = 0
    total_score = 0
    
    questions = course.question_set.all()
    for question in questions:
        total_score += question.grade
        selected_choices = submission.choices.filter(question=question)
        selected_ids = [choice.id for choice in selected_choices]
        if question.is_get_score(selected_ids):
            score += question.grade
            
    context = {
        'course': course,
        'submission': submission,
        'grade': score,
        'total_score': total_score,
    }
    return render(request, 'onlinecourse/exam_result_bootstrap.html', context)
