from django.urls import path

from . import views

app_name = "assessments"

urlpatterns = [
    # Assignments
    path("courses/<slug:slug>/assignments/new/", views.assignment_create, name="assignment_create"),
    path("courses/<slug:slug>/assignments/<int:pk>/", views.assignment_detail, name="assignment"),
    path("courses/<slug:slug>/assignments/<int:pk>/edit/", views.assignment_update, name="assignment_edit"),
    path("courses/<slug:slug>/assignments/<int:pk>/delete/", views.assignment_delete, name="assignment_delete"),
    path("courses/<slug:slug>/assignments/<int:pk>/submit/", views.assignment_submit, name="assignment_submit"),
    path("courses/<slug:slug>/assignments/<int:pk>/submissions/", views.assignment_submissions, name="assignment_submissions"),
    path("submissions/<int:pk>/grade/", views.submission_grade, name="submission_grade"),
    # Quizzes
    path("courses/<slug:slug>/quizzes/new/", views.quiz_create, name="quiz_create"),
    path("courses/<slug:slug>/quizzes/<int:pk>/edit/", views.quiz_update, name="quiz_edit"),
    path("courses/<slug:slug>/quizzes/<int:pk>/delete/", views.quiz_delete, name="quiz_delete"),
    path("quizzes/<int:pk>/", views.quiz_detail, name="quiz_detail"),
    path("quizzes/<int:pk>/start/", views.quiz_start, name="quiz_start"),
    path("quizzes/<int:pk>/questions/", views.quiz_questions, name="quiz_questions"),
    path("quizzes/<int:pk>/questions/new/", views.question_create, name="question_create"),
    path("questions/<int:pk>/edit/", views.question_update, name="question_edit"),
    path("questions/<int:pk>/delete/", views.question_delete, name="question_delete"),
    path("quiz-attempts/<int:pk>/", views.quiz_attempt, name="quiz_attempt"),
    path("quiz-attempts/<int:pk>/result/", views.quiz_result, name="quiz_result"),
    path("quiz-attempts/<int:pk>/grade/", views.quiz_grade_attempt, name="quiz_grade_attempt"),
    # Midterm exams
    path("courses/<slug:slug>/exams/new/", views.exam_create, name="exam_create"),
    path("courses/<slug:slug>/exams/<int:pk>/edit/", views.exam_update, name="exam_edit"),
    path("courses/<slug:slug>/exams/<int:pk>/delete/", views.exam_delete, name="exam_delete"),
    path("exams/<int:pk>/", views.exam_detail, name="exam_detail"),
    path("exams/<int:pk>/start/", views.exam_start, name="exam_start"),
    path("exams/<int:pk>/questions/", views.exam_questions, name="exam_questions"),
    path("exams/<int:pk>/questions/new/", views.exam_question_create, name="exam_question_create"),
    path("exam-questions/<int:pk>/edit/", views.exam_question_update, name="exam_question_edit"),
    path("exam-questions/<int:pk>/delete/", views.exam_question_delete, name="exam_question_delete"),
    path("exam-attempts/<int:pk>/", views.exam_attempt, name="exam_attempt"),
    path("exam-attempts/<int:pk>/result/", views.exam_result, name="exam_result"),
    path("exam-attempts/<int:pk>/grade/", views.exam_grade_attempt, name="exam_grade_attempt"),
]
