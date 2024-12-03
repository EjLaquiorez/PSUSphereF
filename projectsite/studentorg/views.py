from django.shortcuts import render, redirect
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from studentorg.models import Organization, OrgMember, Student, Program, College, Boat
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
from django.contrib import messages

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

# Organization Views
class Organizationlist(ListView):
    model = Organization
    content_object_name = 'organization'
    template_name = 'org_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get("q"):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return qs


class OrganizationCreateView(CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'org_add.html'
    success_url = reverse_lazy('organization-list')

    def form_valid(self, form):
        messages.success(self.request, f"Organization '{form.instance.name}' has been created successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to create the organization. Please check the form for errors.")
        return super().form_invalid(form)


class OrganizationUpdateView(UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'org_edit.html'
    success_url = reverse_lazy('organization-list')

    def form_valid(self, form):
        messages.success(self.request, f"Organization '{form.instance.name}' has been updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to update the organization. Please check the form for errors.")
        return super().form_invalid(form)


class OrganizationDeleteView(DeleteView):
    model = Organization
    template_name = 'org_del.html'
    success_url = reverse_lazy('organization-list')

    def delete(self, request, *args, **kwargs):
        organization = self.get_object()
        messages.success(self.request, f"Organization '{organization.name}' has been deleted successfully!")
        return super().delete(request, *args, **kwargs)


# OrgMember Views
class OrgMemberlist(ListView):
    model = OrgMember
    content_object_name = 'orgmember'
    template_name = 'orgmember_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get("q"):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(date_joined__icontains=query) | Q(student__firstname__icontains=query))
        return qs


class OrgMemberCreateView(CreateView):
    model = OrgMember
    form_class = OrgMemberForm
    template_name = 'orgmember_add.html'
    success_url = reverse_lazy('orgmember-list')

    def form_valid(self, form):
        messages.success(self.request, f"Org Member '{form.instance.student}' has been added to '{form.instance.organization}' successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to add the org member. Please check the form for errors.")
        return super().form_invalid(form)


class OrgMemberUpdateView(UpdateView):
    model = OrgMember
    form_class = OrgMemberForm
    template_name = 'orgmember_edit.html'
    success_url = reverse_lazy('orgmember-list')

    def form_valid(self, form):
        messages.success(self.request, f"Org Member '{form.instance.student}' has been updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to update the org member. Please check the form for errors.")
        return super().form_invalid(form)


class OrgMemberDeleteView(DeleteView):
    model = OrgMember
    template_name = 'orgmember_del.html'
    success_url = reverse_lazy('orgmember-list')

    def delete(self, request, *args, **kwargs):
        org_member = self.get_object()
        messages.success(self.request, f"Org Member '{org_member.student}' has been removed successfully!")
        return super().delete(request, *args, **kwargs)


# Student Views
class StudentList(ListView):
    model = Student
    content_object_name = 'student'
    template_name = 'student_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get("q"):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(student_id__icontains=query) | Q(firstname__icontains=query) | Q(lastname__icontains=query))
        return qs


class StudentCreateView(CreateView):
    model = Student
    form_class = StudentForm
    template_name = 'student_add.html'
    success_url = reverse_lazy('student-list')

    def form_valid(self, form):
        messages.success(self.request, f"Student '{form.instance.firstname} {form.instance.lastname}' has been added successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to add the student. Please check the form for errors.")
        return super().form_invalid(form)


class StudentUpdateView(UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'student_edit.html'
    success_url = reverse_lazy('student-list')

    def form_valid(self, form):
        messages.success(self.request, f"Student '{form.instance.firstname} {form.instance.lastname}' has been updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to update the student. Please check the form for errors.")
        return super().form_invalid(form)


class StudentDeleteView(DeleteView):
    model = Student
    template_name = 'student_del.html'
    success_url = reverse_lazy('student-list')

    def delete(self, request, *args, **kwargs):
        student = self.get_object()
        messages.success(self.request, f"Student '{student.firstname} {student.lastname}' has been deleted successfully!")
        return super().delete(request, *args, **kwargs)


# Program Views
class ProgramList(ListView):
    model = Program
    content_object_name = 'program'
    template_name = 'program_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get("q"):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(prog_name__icontains=query))
        return qs


class ProgramCreateView(CreateView):
    model = Program
    form_class = ProgramForm
    template_name = 'program_add.html'
    success_url = reverse_lazy('program-list')

    def form_valid(self, form):
        messages.success(self.request, f"Program '{form.instance.prog_name}' has been added successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to add the program. Please check the form for errors.")
        return super().form_invalid(form)


class ProgramUpdateView(UpdateView):
    model = Program
    form_class = ProgramForm
    template_name = 'program_edit.html'
    success_url = reverse_lazy('program-list')

    def form_valid(self, form):
        messages.success(self.request, f"Program '{form.instance.prog_name}' has been updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to update the program. Please check the form for errors.")
        return super().form_invalid(form)


class ProgramDeleteView(DeleteView):
    model = Program
    template_name = 'program_del.html'
    success_url = reverse_lazy('program-list')

    def delete(self, request, *args, **kwargs):
        program = self.get_object()
        messages.success(self.request, f"Program '{program.prog_name}' has been deleted successfully!")
        return super().delete(request, *args, **kwargs)


# College Views
class CollegeList(ListView):
    model = College
    content_object_name = 'college'
    template_name = 'college_list.html'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.request.GET.get("q"):
            query = self.request.GET.get('q')
            qs = qs.filter(Q(college_name__icontains=query))
        return qs


class CollegeCreateView(CreateView):
    model = College
    form_class = CollegeForm
    template_name = 'college_add.html'
    success_url = reverse_lazy('college-list')

    def form_valid(self, form):
        messages.success(self.request, f"College '{form.instance.college_name}' has been added successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to add the college. Please check the form for errors.")
        return super().form_invalid(form)


class CollegeUpdateView(UpdateView):
    model = College
    form_class = CollegeForm
    template_name = 'college_edit.html'
    success_url = reverse_lazy('college-list')

    def form_valid(self, form):
        messages.success(self.request, f"College '{form.instance.college_name}' has been updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Failed to update the college. Please check the form for errors.")
        return super().form_invalid(form)


class CollegeDeleteView(DeleteView):
    model = College
    template_name = 'college_del.html'
    success_url = reverse_lazy('college-list')

    def delete(self, request, *args, **kwargs):
        college = self.get_object()
        messages.success(self.request, f"College '{college.college_name}' has been deleted successfully!")
        return super().delete(request, *args, **kwargs)


# Boat Views
class BoatCreateView(CreateView):
    model = Boat
    fields = "__all__"
    template_name = "boat_form.html"
    success_url = reverse_lazy('boat-list')

    def post(self, request, *args, **kwargs):
        length = request.POST.get('length')
        width = request.POST.get('width')
        height = request.POST.get('height')

        # Validate dimensions
        errors = []
        for field_name, value in [('length', length), ('width', width), ('height', height)]:
            try:
                if float(value) <= 0:
                    errors.append(f"{field_name.capitalize()} must be greater than 0.")
            except (ValueError, TypeError):
                errors.append(f"{field_name.capitalize()} must be a valid number.")

        # If errors exist, display them and return to the form
        if errors:
            for error in errors:
                messages.error(request, error)
            return self.form_invalid(self.get_form())

        # Call the parent's post() if validation passes
        return super().post(request, *args, **kwargs)


class BoatUpdateView(UpdateView):
    model = Boat
    fields = "__all__"
    template_name = "boat_form.html"
    success_url = reverse_lazy('boat-list')

    def post(self, request, *args, **kwargs):
        length = request.POST.get('length')
        width = request.POST.get('width')
        height = request.POST.get('height')

        # Validate dimensions
        errors = []
        for field_name, value in [('length', length), ('width', width), ('height', height)]:
            try:
                if float(value) <= 0:
                    errors.append(f"{field_name.capitalize()} must be greater than 0.")
            except (ValueError, TypeError):
                errors.append(f"{field_name.capitalize()} must be a valid number.")

        # If errors exist, display them and return to the form
        if errors:
            for error in errors:
                messages.error(request, error)
            return self.form_invalid(self.get_form())

        # Call the parent's post() if validation passes
        return super().post(request, *args, **kwargs)
    
class BoatDeleteView(DeleteView):
    model = Boat
    template_name = 'boat_confirm_delete.html'
    success_url = reverse_lazy('boat-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['boat'] = self.get_object()  # Ensure the boat object is available in the template
        return context

    def delete(self, request, *args, **kwargs):
        boat = self.get_object()
        try:
            result = super().delete(request, *args, **kwargs)  # Delete the boat
            messages.success(request, f"Boat '{boat.boat_name}' has been deleted successfully!")
            return result
        except Exception as e:
            messages.error(request, f"Error deleting boat: {str(e)}")
            return redirect('boat-list')