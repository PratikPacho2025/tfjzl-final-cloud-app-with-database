from django.contrib.auth.models import User
from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from .models import (
    Choice,
    Course,
    Enrollment,
    Instructor,
    Learner,
    Lesson,
    Question,
    Submission,
)


class AssessmentFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='learner',
            password='test-password',
        )
        self.other_user = User.objects.create_user(
            username='other-learner',
            password='test-password',
        )
        self.course = Course.objects.create(
            name='Django Assessment',
            description='Assessment test course',
        )
        self.question = Question.objects.create(
            course=self.course,
            content='Which framework is this project using?',
            grade=5,
        )
        self.correct_choice = Choice.objects.create(
            question=self.question,
            content='Django',
            is_correct=True,
        )
        self.incorrect_choice = Choice.objects.create(
            question=self.question,
            content='Flask',
            is_correct=False,
        )
        self.multi_question = Question.objects.create(
            course=self.course,
            content='Select database systems.',
            grade=5,
        )
        self.multi_correct_1 = Choice.objects.create(
            question=self.multi_question,
            content='SQLite',
            is_correct=True,
        )
        self.multi_correct_2 = Choice.objects.create(
            question=self.multi_question,
            content='PostgreSQL',
            is_correct=True,
        )
        self.multi_incorrect = Choice.objects.create(
            question=self.multi_question,
            content='Nginx',
            is_correct=False,
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            mode=Enrollment.HONOR,
        )

    def test_course_details_show_lessons_and_assessment(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'onlinecourse:course_details',
                kwargs={'pk': self.course.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.name)
        self.assertContains(response, 'Course Lessons')
        self.assertContains(response, self.question.content)
        self.assertContains(response, self.correct_choice.content)

    def test_enrolled_learner_submission_is_scored_on_server(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                'onlinecourse:submit',
                kwargs={'course_id': self.course.pk},
            ),
            {
                f'choice_{self.question.pk}': str(self.correct_choice.pk),
                f'choice{self.multi_correct_1.pk}': 'true',
                f'choice{self.multi_correct_2.pk}': 'true',
            },
        )

        submission = Submission.objects.get(enrollment=self.enrollment)
        result_url = reverse(
            'onlinecourse:show_exam_result',
            kwargs={
                'course_id': self.course.pk,
                'submission_id': submission.pk,
            },
        )

        self.assertRedirects(response, result_url)
        result = self.client.get(result_url)
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, 'Congratulations!')
        self.assertContains(result, '10 / 10')
        self.assertContains(result, '100%')
        self.assertEqual(result.context['possible'], 10)

    def test_incorrect_answer_does_not_earn_marks(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                'onlinecourse:submit',
                kwargs={'course_id': self.course.pk},
            ),
            {
                f'choice_{self.question.pk}': str(self.incorrect_choice.pk),
                f'choice{self.multi_correct_1.pk}': 'true',
            },
        )

        submission = Submission.objects.get(enrollment=self.enrollment)
        result = self.client.get(
            reverse(
                'onlinecourse:show_exam_result',
                kwargs={
                    'course_id': self.course.pk,
                    'submission_id': submission.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertContains(result, '0 / 10')
        self.assertContains(result, '0%')
        self.assertContains(result, 'Incorrect answer')

    def test_submission_requires_authentication_and_enrollment(self):
        submit_url = reverse(
            'onlinecourse:submit',
            kwargs={'course_id': self.course.pk},
        )

        response = self.client.post(
            submit_url,
            {f'choice_{self.question.pk}': str(self.correct_choice.pk)},
        )
        self.assertRedirects(
            response,
            reverse('onlinecourse:login'),
        )

        self.client.force_login(self.other_user)
        response = self.client.post(
            submit_url,
            {f'choice_{self.question.pk}': str(self.correct_choice.pk)},
        )
        self.assertEqual(response.status_code, 404)

    def test_learner_cannot_view_another_learners_result(self):
        submission = Submission.objects.create(enrollment=self.enrollment)
        submission.choices.add(self.correct_choice)

        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse(
                'onlinecourse:show_exam_result',
                kwargs={
                    'course_id': self.course.pk,
                    'submission_id': submission.pk,
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_choice_is_ignored_for_scoring(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                'onlinecourse:submit',
                kwargs={'course_id': self.course.pk},
            ),
            {
                f'choice_{self.question.pk}': str(self.correct_choice.pk),
                'choice999999': 'true',
            },
        )
        self.assertEqual(response.status_code, 302)

        submission = Submission.objects.get(enrollment=self.enrollment)
        self.assertEqual(submission.choices.count(), 1)
        self.assertEqual(submission.choices.first().pk, self.correct_choice.pk)

    def test_exam_result_requires_owner(self):
        submission = Submission.objects.create(enrollment=self.enrollment)
        submission.choices.add(self.correct_choice)

        self.client.force_login(self.user)
        own_result = self.client.get(
            reverse(
                'onlinecourse:show_exam_result',
                kwargs={
                    'course_id': self.course.pk,
                    'submission_id': submission.pk,
                },
            )
        )
        self.assertEqual(own_result.status_code, 200)
        self.assertIn('possible', own_result.context)

    def test_submission_string_representation(self):
        submission = Submission.objects.create(enrollment=self.enrollment)
        self.assertIn(f"Submission(id={submission.id}", str(submission))


class AdminRegistrationTests(TestCase):
    def test_required_models_registered_in_admin(self):
        for model in (
            Course,
            Lesson,
            Instructor,
            Learner,
            Enrollment,
            Question,
            Choice,
            Submission,
        ):
            self.assertIn(model, admin.site._registry)
