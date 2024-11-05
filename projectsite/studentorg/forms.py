from django.forms import ModelForm
from django import forms
from .models import Organization,OrgMember,Student,Program,College

class OrganizationForm(ModelForm):
    class Meta:
        model = Organization
        fields = "__all__"
    
class OrgMemberForm(ModelForm):
    class Meta:
        model = OrgMember
        fields = "__all__"
        widgets = {
            'date_joined': forms.DateInput(attrs={'type':'date'})
        }

class StudentForm(ModelForm):
    class Meta:
        model = Student
        fields = "__all__"
    
class ProgramForm(ModelForm):
    class Meta:
        model = Program
        fields = "__all__"

class CollegeForm(ModelForm):
    class Meta:
        model = College
        fields = "__all__"