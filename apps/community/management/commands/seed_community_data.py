from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.careers.models import CompanyProfile
from apps.core.models import University
from apps.community.models import ForumCategory, ForumComment, ForumPost

User = get_user_model()

CATEGORIES = [
    ("Companies", "Connect with employers, recruiters, and company representatives."),
    ("Universities", "Discuss partnerships, research, and university opportunities."),
    ("Schools", "Coordinate with schools, teachers, and student advisors."),
    ("Students", "Peer discussions, study groups, and questions."),
    ("Alumni", "Stay connected with graduates and mentors."),
    ("Career", "Jobs, internships, and career advice."),
    ("Courses", "Questions and discussion about courses."),
    ("Events", "Workshops, seminars, and campus events."),
    ("Scholarships", "Scholarship opportunities and application help."),
    ("General", "Open discussion for all learners."),
]

UNIVERSITIES = [
    ("royal-university-phnom-penh", "Royal University of Phnom Penh", "RUPP"),
    ("institute-technology-cambodia", "Institute of Technology of Cambodia", "ITC"),
]

POSTS = [
    (
        "Welcome to the Employers and Partners forum",
        "Companies",
        "company",
        "Welcome! This is the space for companies to share opportunities, meet learners, and build partnerships with our schools and universities.",
        [("student", "Thank you — looking forward to connecting with employers here."), ("university", "We would love to explore joint projects with your teams.")],
    ),
    (
        "Internship openings for final-year students",
        "Companies",
        "company2",
        "We have paid software internships available in Phnom Penh. Students can apply through the Jobs and internships page and attach their CV.",
        [("student", "Are remote internships available for students outside Phnom Penh?"), ("company2", "Yes, two of our roles are remote-friendly.")],
    ),
    (
        "What should a strong internship application include?",
        "Companies",
        "company3",
        "A one-page CV, a short cover letter, and links to projects are enough. We care about your willingness to learn more than years of experience.",
        [("school", "We will share this guidance with our final-year classes.")],
    ),
    (
        "University partnership and credit transfer",
        "Universities",
        "university",
        "We are exploring credit transfer for platform courses. University partners can post here to discuss alignment and student recognition.",
        [("company", "Employers would welcome clear skill badges alongside transcripts."), ("university2", "Our faculty is interested in a pilot next term.")],
    ),
    (
        "Research collaboration with local universities",
        "Universities",
        "university2",
        "Our research group is looking for partners in data analytics and education technology. Feel free to comment if you would like to collaborate.",
        [("student", "Are student research assistants welcome?"), ("university", "Yes, joint supervision with faculty is possible.")],
    ),
    (
        "Campus recruitment fair — express your interest",
        "Universities",
        "university",
        "We are planning a campus recruitment fair with companies, schools, and universities. Add your organisation's interests in the comments.",
        [("company2", "We would like to reserve a booth."), ("school", "Our students would love to attend.")],
    ),
    (
        "School–industry bridge programme",
        "Schools",
        "school",
        "We are connecting secondary school students with companies and universities through short workshops and campus visits.",
        [("company", "Our engineers can run an introductory web workshop."), ("university", "We can host the campus visit.")],
    ),
    (
        "Career guidance for high-school students",
        "Schools",
        "school2",
        "What topics should we cover in our career guidance sessions: CV writing, interview practice, or study pathways?",
        [("student", "Interview practice helped me the most."), ("company3", "We can provide mock interview volunteers.")],
    ),
    (
        "Teacher exchange and shared learning resources",
        "Schools",
        "school",
        "Teachers from schools and universities can share lesson ideas and learning materials here to support each other.",
        [("university", "We will share our open teaching materials.")],
    ),
    (
        "Study group: Introduction to Web Development",
        "Students",
        "student",
        "Anyone taking WEB101 want to form a weekly study group? We can work through the assignments together.",
        [("student", "Count me in!"), ("school", "I can help facilitate if useful.")],
    ),
    (
        "CV tips from a recruiter",
        "Career",
        "company4",
        "Keep your CV to one page, lead with your strongest project, and always proofread. Upload it in My CVs before applying.",
        [("student", "Very helpful, thank you!")],
    ),
    (
        "Scholarship application questions",
        "Scholarships",
        "university2",
        "Post your scholarship questions here and our partners will answer. Application deadlines are listed on the Scholarships page.",
        [("student", "Can final-year students apply?"), ("university", "Yes, most programmes accept final-year applicants.")],
    ),
    (
        "Workshop: Interview preparation",
        "Events",
        "company5",
        "Join our free interview preparation workshop. Company representatives will run mock interviews and give feedback.",
        [("school", "Can we bring a group of students?")],
    ),
    (
        "Alumni mentorship network",
        "Alumni",
        "school2",
        "Graduates can mentor current students here. Share your field, availability, and how you can help.",
        [("company", "Several of our staff would like to mentor.")],
    ),
    (
        "Platform feedback and suggestions",
        "General",
        "student",
        "Use this thread to share feedback about courses, exams, jobs, or community features. All stakeholders are welcome.",
        [("company", "The CV upload flow works well for our hiring process."), ("university", "More exam date filters would be useful.")],
    ),
]

AUTHORS = {
    "company": ("company0001@smartlearning.local", User.Role.COMPANY, "Hiring", "Partner"),
    "company2": ("company0002@smartlearning.local", User.Role.COMPANY, "Careers", "Team"),
    "company3": ("company0003@smartlearning.local", User.Role.COMPANY, "People", "Team"),
    "company4": ("company0004@smartlearning.local", User.Role.COMPANY, "Talent", "Partner"),
    "company5": ("company0005@smartlearning.local", User.Role.COMPANY, "Learning", "Partner"),
    "university": ("university0001@smartlearning.local", User.Role.UNIVERSITY_ADMIN, "University", "Partner"),
    "university2": ("university0002@smartlearning.local", User.Role.UNIVERSITY_ADMIN, "Academic", "Partner"),
    "school": ("school0001@smartlearning.local", User.Role.TEACHER, "School", "Teacher"),
    "school2": ("school0002@smartlearning.local", User.Role.TEACHER, "School", "Advisor"),
    "student": ("student@smartlearning.local", User.Role.STUDENT, "Demo", "Student"),
}


class Command(BaseCommand):
    help = "Seed forum categories, organisation authors, discussions, and replies (idempotent)."

    def handle(self, *args, **options):
        for name, description in CATEGORIES:
            ForumCategory.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name), "description": description},
            )

        for code, name, short_name in UNIVERSITIES:
            University.objects.get_or_create(
                code=code, defaults={"name": name, "short_name": short_name}
            )

        authors = {}
        for key, (email, role, first_name, last_name) in AUTHORS.items():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"role": role, "first_name": first_name, "last_name": last_name},
            )
            if created:
                user.set_password("Partner@12345")
                user.save(update_fields=["password"])
            authors[key] = user
            if role == User.Role.COMPANY:
                profile, _ = CompanyProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "company_name": f"{first_name} {last_name}",
                        "contact_email": email,
                        "is_approved": True,
                    },
                )
                authors[f"{key}_company"] = profile

        categories = {category.name: category for category in ForumCategory.objects.all()}
        posts_created = 0
        comments_created = 0
        for title, category_name, author_key, body, replies in POSTS:
            post, was_created = ForumPost.objects.get_or_create(
                title=title,
                defaults={
                    "category": categories[category_name],
                    "author": authors[author_key],
                    "body": body,
                },
            )
            posts_created += int(was_created)
            for reply_author_key, reply_body in replies:
                _, comment_created = ForumComment.objects.get_or_create(
                    post=post,
                    author=authors[reply_author_key],
                    body=reply_body,
                )
                comments_created += int(comment_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Community data ready: {posts_created} discussions and "
                f"{comments_created} replies created across "
                f"{ForumCategory.objects.count()} categories."
            )
        )
