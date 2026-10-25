from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Choice, Course, Enrollment, Question, Submission


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
        self.assertContains(result, '5 / 5')
        self.assertContains(result, '100%')

    def test_incorrect_answer_does_not_earn_marks(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                'onlinecourse:submit',
                kwargs={'course_id': self.course.pk},
            ),
            {
                f'choice_{self.question.pk}': str(self.incorrect_choice.pk),
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
        self.assertContains(result, '0 / 5')
        self.assertContains(result, '0%')

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
