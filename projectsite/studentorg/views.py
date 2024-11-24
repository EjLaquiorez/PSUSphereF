from django.shortcuts import render
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from studentorg.models import Organization, OrgMember, Student, Program, College
from studentorg.forms import OrganizationForm, OrgMemberForm, StudentForm, ProgramForm, CollegeForm
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg
import json

from typing import Any
from django.db.models.query import QuerySet
from django.db.models import Q
from django.views.generic import TemplateView
from django.db.models.functions import TruncMonth
from django.db.models.functions import ExtractYear
from django.utils import timezone
from datetime import datetime, timedelta

# Create your views here.

@method_decorator(login_required, name='dispatch')
class HomePageView(TemplateView):
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the count of students per college through their program
        college_data = Student.objects.values('program__college__college_name')\
                                    .annotate(count=Count('id'))
        
        # Prepare data for the chart    
        college_labels = [item['program__college__college_name'] for item in college_data]
        college_counts = [item['count'] for item in college_data]
        
        # New: Organization membership data
        org_data = OrgMember.objects.values('organization__name')\
                                   .annotate(member_count=Count('id'))\
                                   .order_by('-member_count')
        
        org_labels = [item['organization__name'] for item in org_data]
        org_counts = [item['member_count'] for item in org_data]

        # Monthly membership growth
        monthly_data = OrgMember.objects.annotate(
            month=TruncMonth('date_joined')
        ).values('month').annotate(
            new_members=Count('id')
        ).order_by('month')

        timeline_labels = [item['month'].strftime('%B %Y') for item in monthly_data]
        timeline_counts = [item['new_members'] for item in monthly_data]
        
        # Get program distribution data
        programs = Program.objects.all()
        program_labels = [program.prog_name for program in programs]
        program_counts = [Student.objects.filter(program=program).count() 
                         for program in programs]

        # Get yearly data for the past 4 years
        current_year = timezone.now().year
        years = list(range(current_year - 3, current_year + 1))
        
        # Get total students per year (based on created_at)
        yearly_students = []
        graduation_rates = []
        
        for year in years:
            # Count students created in this year
            student_count = Student.objects.filter(
                created_at__year=year
            ).count()
            yearly_students.append(student_count)
            
            # Calculate graduation rate (example: 80-95%)
            # You might want to adjust this based on your actual graduation tracking
            total_students = Student.objects.filter(
                created_at__year=year
            ).count()
            
            # Assuming you have some way to track graduated students
            # This is a placeholder - adjust according to your model structure
            graduated_students = Student.objects.filter(
                created_at__year=year,
                # Add your graduation criteria here
                # For example: status='GRADUATED'
            ).count()
            
            # Calculate graduation rate
            graduation_rate = (
                (graduated_students / total_students * 100)
                if total_students > 0 
                else 0
            )
            graduation_rates.append(round(graduation_rate, 1))

        # Prepare bubble chart data
        organizations = Organization.objects.all()
        bubble_data = []
        
        for org in organizations:
            members_count = OrgMember.objects.filter(organization=org).count()
            if members_count > 0:
                # Get all members' join dates and calculate average days manually
                member_dates = OrgMember.objects.filter(organization=org).values_list('date_joined', flat=True)
                today = timezone.now().date()
                
                # Calculate average days since joining
                total_days = sum((today - date_joined).days for date_joined in member_dates)
                avg_days = total_days / len(member_dates) if member_dates else 0
                
                # Count students in the organization's college
                college_students = Student.objects.filter(
                    program__college=org.college
                ).count() if org.college else 0
                
                bubble_data.append({
                    'label': org.name,
                    'data': [{
                        'x': members_count,
                        'y': round(avg_days, 1),  # Round to 1 decimal place
                        'r': min(max(college_students / 5, 5), 50),  # Scale bubble size between 5 and 50
                        'org': org.name
                    }]
                })

        # Add Radar Chart Data
        radar_labels = ['Member Count', 'College Diversity', 'Program Diversity', 
                       'Member Retention', 'Growth Rate']
        
        radar_datasets = []
        
        # Debug print
        print("Number of organizations:", organizations.count())
        
        for org in organizations:
            members = OrgMember.objects.filter(organization=org)
            member_count = members.count()
            
            # Debug print
            print(f"Processing org: {org.name}, member count: {member_count}")
            
            if member_count > 0:
                # Member count score
                max_members = OrgMember.objects.values('organization')\
                    .annotate(count=Count('id'))\
                    .order_by('-count').first()
                max_member_count = max_members['count'] if max_members else 0
                member_score = (member_count / max_member_count * 100) if max_member_count > 0 else 0
                
                # College diversity score
                college_count = members.select_related('student__program__college')\
                    .values('student__program__college')\
                    .distinct().count()
                total_colleges = College.objects.count()
                college_score = (college_count / total_colleges * 100) if total_colleges > 0 else 0
                
                # Program diversity score
                program_count = members.select_related('student__program')\
                    .values('student__program')\
                    .distinct().count()
                total_programs = Program.objects.count()
                program_score = (program_count / total_programs * 100) if total_programs > 0 else 0
                
                # Member retention score
                six_months_ago = timezone.now().date() - timedelta(days=180)
                retained_members = members.filter(date_joined__lte=six_months_ago).count()
                retention_score = (retained_members / member_count * 100) if member_count > 0 else 0
                
                # Growth rate
                three_months_ago = timezone.now().date() - timedelta(days=90)
                new_members = members.filter(date_joined__gte=three_months_ago).count()
                growth_score = (new_members / member_count * 100) if member_count > 0 else 0
                
                dataset = {
                    'label': org.name,
                    'data': [
                        round(member_score, 1),
                        round(college_score, 1),
                        round(program_score, 1),
                        round(retention_score, 1),
                        round(growth_score, 1)
                    ],
                    'fill': True,
                    'backgroundColor': f'rgba({hash(org.name) % 255}, {(hash(org.name) >> 8) % 255}, {(hash(org.name) >> 16) % 255}, 0.2)',
                    'borderColor': f'rgb({hash(org.name) % 255}, {(hash(org.name) >> 8) % 255}, {(hash(org.name) >> 16) % 255})',
                    'pointBackgroundColor': f'rgb({hash(org.name) % 255}, {(hash(org.name) >> 8) % 255}, {(hash(org.name) >> 16) % 255})',
                    'pointBorderColor': '#fff',
                    'pointHoverBackgroundColor': '#fff',
                    'pointHoverBorderColor': f'rgb({hash(org.name) % 255}, {(hash(org.name) >> 8) % 255}, {(hash(org.name) >> 16) % 255})'
                }
                
                radar_datasets.append(dataset)

        # Update context with real data
        context.update({
            'college_labels': json.dumps(college_labels),
            'college_counts': json.dumps(college_counts),
            'org_labels': json.dumps(org_labels),
            'org_counts': json.dumps(org_counts),
            'timeline_labels': json.dumps(timeline_labels),
            'timeline_counts': json.dumps(timeline_counts),
            'program_labels': json.dumps(program_labels),
            'program_counts': json.dumps(program_counts),
            'yearly_students': json.dumps(yearly_students),
            'graduation_rates': json.dumps(graduation_rates),
            'years': json.dumps([str(year) for year in years]),
            'bubble_data': json.dumps(bubble_data),
            'radar_labels': json.dumps(radar_labels),
            'radar_datasets': json.dumps(radar_datasets),
        })
        return context

class Organizationlist(ListView):
    model = Organization
    content_object_name = 'organization'
    template_name = 'org_list.html'
    paginate_by = 5
    
    def get_queryset(self, *args, **kwargs):
        qs = super(Organizationlist, self).get_queryset(*args, **kwargs)
        if self.request.GET.get("q") != None:
            query = self.request.GET.get('q')
            qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return qs

class OrganizationCreateView(CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'org_add.html'
    success_url = reverse_lazy('organization-list')

class OrganizationUpdateView(UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'org_edit.html'
    success_url = reverse_lazy('organization-list')

class OrganizationDeleteView(DeleteView):
    model = Organization
#    form_class = OrganizationForm
    template_name = 'org_del.html'
    success_url = reverse_lazy('organization-list')

class OrgMemberlist(ListView):
    model = OrgMember
    content_object_name = 'orgmember'
    template_name = 'orgmember_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super(OrgMemberlist, self).get_queryset(*args, **kwargs)
        if self.request.GET.get("q") != None:
            query = self.request.GET.get('q')
            qs = qs.filter(Q(date_joined__icontains=query) | Q(student_firstname__icontains=query)) 
        return qs

class OrgMemberCreateView(CreateView):
    model = OrgMember
    form_class = OrgMemberForm
    template_name = 'orgmember_add.html'
    success_url = reverse_lazy('orgmember-list')

class OrgMemberUpdateView(UpdateView):
    model = OrgMember
    form_class = OrgMemberForm
    template_name = 'orgmember_edit.html'
    success_url = reverse_lazy('orgmember-list')

class OrgMemberDeleteView(DeleteView):
    model = OrgMember
#    form_class = OrgMemberForm
    template_name = 'orgmember_del.html'
    success_url = reverse_lazy('orgmember-list')

class StudentList(ListView):
    model = Student
    content_object_name = 'student'
    template_name = 'student_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super(StudentList, self).get_queryset(*args, **kwargs)
        if self.request.GET.get("q") != None:
            query = self.request.GET.get('q')
            qs = qs.filter(Q(student_id__icontains=query) | Q(firstname__icontains=query) | Q(lastname__icontains=query) | Q(middlename__icontains=query))
        return qs

class StudentCreateView(CreateView):
    model = Student
    form_class = StudentForm
    template_name = 'orgmember_add.html'
    success_url = reverse_lazy('student-list')

class StudentUpdateView(UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'student_edit.html'
    success_url = reverse_lazy('student-list')

class StudentDeleteView(DeleteView):
    model = Student
#    form_class = StudentForm
    template_name = 'student_del.html'
    success_url = reverse_lazy('student-list')


class ProgramList(ListView):
    model = Program
    content_object_name = 'program'
    template_name = 'program_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super(ProgramList, self).get_queryset(*args, **kwargs)
        if self.request.GET.get("q") != None:
            query = self.request.GET.get('q')
            qs = qs.filter(Q(prog_name__icontains=query))
        return qs

class ProgramCreateView(CreateView):
    model = Program
    form_class = ProgramForm
    template_name = 'program_add.html'
    success_url = reverse_lazy('program-list')

class ProgramUpdateView(UpdateView):
    model = Program
    form_class = ProgramForm
    template_name = 'program_edit.html'
    success_url = reverse_lazy('program-list')

class ProgramDeleteView(DeleteView):
    model = Program
#    form_class = ProgramForm
    template_name = 'program_del.html'
    success_url = reverse_lazy('program-list')

class CollegeList(ListView):
    model = College
    content_object_name = 'college'
    template_name = 'college_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super(CollegeList, self).get_queryset(*args, **kwargs)
        if self.request.GET.get("q") != None:
            query = self.request.GET.get('q')
            qs = qs.filter(Q(college_name__icontains=query))
        return qs

class CollegeCreateView(CreateView):
    model = College
    form_class = CollegeForm
    template_name = 'college_add.html'
    success_url = reverse_lazy('college-list')

class CollegeUpdateView(UpdateView):
    model = College
    form_class = CollegeForm
    template_name = 'college_edit.html'
    success_url = reverse_lazy('college-list')

class CollegeDeleteView(DeleteView):
    model = College
#    form_class = CollegeForm
    template_name = 'college_del.html'
    success_url = reverse_lazy('college-list')