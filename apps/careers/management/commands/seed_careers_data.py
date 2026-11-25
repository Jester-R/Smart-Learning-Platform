from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.careers.models import CompanyProfile, Job, JobPostingPackage

User = get_user_model()

COMPANIES = [
    (
        "Phnom Penh Digital Labs",
        "company0001@smartlearning.local",
        "A product studio building web and mobile experiences for local businesses.",
        "https://ppdigitallabs.example.com",
        [
            ("Frontend Developer", "full_time", "Phnom Penh", 800, 1500),
            ("Backend Developer", "full_time", "Phnom Penh", 900, 1700),
            ("Frontend Development Intern", "internship", "Phnom Penh", 200, 350),
            ("Backend Development Intern", "internship", "Phnom Penh", 200, 350),
            ("UI/UX Designer", "full_time", "Phnom Penh", 700, 1300),
            ("QA Engineer", "contract", "Phnom Penh", 600, 1000),
            ("Remote Support Engineer", "remote", "Remote", 500, 900),
            ("Data Analyst", "part_time", "Phnom Penh", 400, 800),
        ],
    ),
    (
        "Angkor Cloud Solutions",
        "company0002@smartlearning.local",
        "Cloud infrastructure and managed hosting provider for growing teams.",
        "https://ankorcloud.example.com",
        [
            ("Cloud Engineer", "full_time", "Phnom Penh", 1000, 1800),
            ("DevOps Engineer", "full_time", "Phnom Penh", 1100, 2000),
            ("Cloud Operations Intern", "internship", "Phnom Penh", 250, 400),
            ("Junior DevOps Intern", "internship", "Remote", 250, 400),
            ("Network Engineer", "full_time", "Siem Reap", 700, 1200),
            ("Systems Administrator", "contract", "Phnom Penh", 600, 1100),
            ("Platform Support Specialist", "remote", "Remote", 500, 900),
            ("Security Analyst", "full_time", "Phnom Penh", 900, 1600),
        ],
    ),
    (
        "Mekong Tech Studio",
        "company0003@smartlearning.local",
        "Digital product studio specialising in mobile apps and design systems.",
        "https://mekongtech.example.com",
        [
            ("Full-Stack Developer", "full_time", "Phnom Penh", 900, 1700),
            ("Mobile App Developer", "full_time", "Phnom Penh", 800, 1500),
            ("Product Designer", "full_time", "Phnom Penh", 750, 1400),
            ("Frontend Development Intern", "internship", "Phnom Penh", 200, 350),
            ("Mobile Development Intern", "internship", "Phnom Penh", 200, 350),
            ("React Developer", "contract", "Remote", 700, 1300),
            ("QA Tester", "part_time", "Phnom Penh", 350, 700),
            ("Technical Writer", "remote", "Remote", 400, 800),
        ],
    ),
    (
        "Khmer Innovation Hub",
        "company0004@smartlearning.local",
        "Incubator helping early-stage startups launch and grow in Cambodia.",
        "https://khmerhub.example.com",
        [
            ("Product Manager", "full_time", "Phnom Penh", 1000, 1800),
            ("Business Development Executive", "full_time", "Phnom Penh", 700, 1400),
            ("Marketing Specialist", "full_time", "Phnom Penh", 650, 1200),
            ("Startup Intern", "internship", "Phnom Penh", 200, 300),
            ("Marketing Intern", "internship", "Phnom Penh", 180, 300),
            ("Community Manager", "part_time", "Remote", 350, 700),
            ("Event Coordinator", "contract", "Phnom Penh", 300, 600),
            ("Data Entry Assistant", "part_time", "Phnom Penh", 250, 450),
        ],
    ),
    (
        "Cambodia Fintech Co.",
        "company0005@smartlearning.local",
        "Financial technology company building accessible payment solutions.",
        "https://cambodiafintech.example.com",
        [
            ("Payment Systems Engineer", "full_time", "Phnom Penh", 1100, 2100),
            ("Risk Analyst", "full_time", "Phnom Penh", 800, 1500),
            ("Compliance Officer", "full_time", "Phnom Penh", 750, 1400),
            ("Fintech Product Intern", "internship", "Phnom Penh", 250, 400),
            ("Data Analytics Intern", "internship", "Phnom Penh", 250, 400),
            ("Customer Support Specialist", "full_time", "Phnom Penh", 400, 700),
            ("Mobile Banking Developer", "contract", "Remote", 900, 1700),
            ("Fraud Analyst", "remote", "Remote", 700, 1300),
        ],
    ),
    (
        "Siem Reap Webworks",
        "company0006@smartlearning.local",
        "Web design and development agency serving tourism and hospitality clients.",
        "https://siemreapwebworks.example.com",
        [
            ("WordPress Developer", "full_time", "Siem Reap", 600, 1100),
            ("Web Designer", "contract", "Remote", 500, 1000),
            ("Web Development Intern", "internship", "Siem Reap", 180, 300),
            ("Graphic Design Intern", "internship", "Siem Reap", 180, 300),
            ("SEO Specialist", "part_time", "Remote", 350, 700),
            ("E-commerce Developer", "full_time", "Siem Reap", 700, 1300),
            ("Content Writer", "remote", "Remote", 300, 600),
            ("Website Maintenance Technician", "part_time", "Siem Reap", 250, 500),
        ],
    ),
    (
        "Tonle Sap Analytics",
        "company0007@smartlearning.local",
        "Data analytics consultancy turning complex data into clear decisions.",
        "https://tonlesapanalytics.example.com",
        [
            ("Data Scientist", "full_time", "Phnom Penh", 1100, 2000),
            ("Business Intelligence Analyst", "full_time", "Phnom Penh", 800, 1500),
            ("Data Engineering Intern", "internship", "Remote", 250, 400),
            ("Machine Learning Intern", "internship", "Phnom Penh", 250, 400),
            ("Database Administrator", "full_time", "Phnom Penh", 900, 1600),
            ("Reporting Analyst", "contract", "Remote", 600, 1100),
            ("Statistics Tutor", "part_time", "Phnom Penh", 300, 600),
            ("Analytics Consultant", "remote", "Remote", 800, 1500),
        ],
    ),
    (
        "Future Skills Academy",
        "company0008@smartlearning.local",
        "Training provider offering practical tech and career skills programmes.",
        "https://futureskills.example.com",
        [
            ("Career Coach", "full_time", "Phnom Penh", 600, 1100),
            ("Curriculum Developer", "full_time", "Phnom Penh", 700, 1300),
            ("Training Coordinator", "full_time", "Phnom Penh", 500, 900),
            ("Teaching Assistant Intern", "internship", "Phnom Penh", 150, 250),
            ("Student Support Intern", "internship", "Remote", 150, 250),
            ("Online Instructor", "contract", "Remote", 500, 1000),
            ("Admissions Officer", "part_time", "Phnom Penh", 300, 600),
            ("Learning Experience Designer", "remote", "Remote", 700, 1300),
        ],
    ),
]

RESPONSIBILITIES = {
    "full_time": "Work with the team to deliver agreed goals, document progress, and support continuous improvement.",
    "part_time": "Support ongoing projects on a flexible schedule and report progress to the team lead.",
    "internship": "Learn by contributing to real projects, joining code or design reviews, and documenting your work.",
    "contract": "Deliver the agreed scope on schedule and collaborate with stakeholders on acceptance criteria.",
    "remote": "Collaborate asynchronously with the team, keep clear written updates, and meet agreed milestones.",
}

REQUIREMENTS = {
    "full_time": "Relevant experience, strong communication skills, and a portfolio or examples of past work.",
    "part_time": "Relevant skills, reliability, and the ability to manage your time independently.",
    "internship": "Currently studying or recently graduated, foundational knowledge, and eagerness to learn.",
    "contract": "Proven experience in the role, clear references, and the ability to work independently.",
    "remote": "Reliable internet connection, strong written communication, and experience with remote collaboration tools.",
}


class Command(BaseCommand):
    help = "Seed approved companies and published jobs/internships for the careers page (idempotent)."

    def handle(self, *args, **options):
        packages = list(JobPostingPackage.objects.filter(is_active=True).order_by("price"))
        companies_created = 0
        jobs_created = 0

        for name, email, description, website, positions in COMPANIES:
            first, last = name.split()[0], name.split()[-1]
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "role": User.Role.COMPANY,
                    "first_name": first[:30],
                    "last_name": last[:30],
                },
            )
            if user_created:
                user.set_password("Company@12345")
                user.save(update_fields=["password"])
            company, company_created = CompanyProfile.objects.get_or_create(
                company_name=name,
                defaults={
                    "user": user,
                    "description": description,
                    "website": website,
                    "contact_email": email,
                    "is_approved": True,
                },
            )
            companies_created += int(company_created)

            for index, (title, job_type, location, salary_min, salary_max) in enumerate(positions):
                package = packages[index % len(packages)] if packages else None
                _, job_created = Job.objects.get_or_create(
                    company=company,
                    title=title,
                    defaults={
                        "description": (
                            f"{name} is hiring a {title} to join our team in {location}. "
                            "You will work on meaningful projects with supportive colleagues and have "
                            "clear opportunities to grow your skills."
                        ),
                        "responsibilities": RESPONSIBILITIES[job_type],
                        "requirements": REQUIREMENTS[job_type],
                        "location": location,
                        "job_type": job_type,
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "application_deadline": timezone.now() + timedelta(days=30 + index * 3),
                        "package": package,
                        "status": Job.Status.PUBLISHED,
                        "is_approved": True,
                    },
                )
                jobs_created += int(job_created)

        total = Job.objects.filter(status=Job.Status.PUBLISHED, is_approved=True).count()
        internships = Job.objects.filter(
            status=Job.Status.PUBLISHED,
            is_approved=True,
            job_type=Job.JobType.INTERNSHIP,
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Careers data ready: {companies_created} companies and {jobs_created} positions created. "
                f"Page now lists {total} positions ({internships} internships)."
            )
        )
