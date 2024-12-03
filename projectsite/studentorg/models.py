from django.db import models

class BaseModel(models.Model):
    """Abstract base model with created and updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class College(BaseModel):
    """Model representing a college."""
    college_name = models.CharField(max_length=150)

    def __str__(self):
        return self.college_name


class Program(BaseModel):
    """Model representing a program."""
    prog_name = models.CharField(max_length=150)
    college = models.ForeignKey(College, on_delete=models.CASCADE)

    def __str__(self):
        return self.prog_name


class Organization(BaseModel):
    """Model representing an organization."""
    name = models.CharField(max_length=250)
    college = models.ForeignKey(College, null=True, blank=True, on_delete=models.CASCADE)
    description = models.CharField(max_length=500)

    def __str__(self):
        return self.name


class Student(BaseModel):
    """Model representing a student."""
    student_id = models.CharField(max_length=15)
    lastname = models.CharField(max_length=25, verbose_name="Last Name" )
    firstname = models.CharField(max_length=25, verbose_name="First Name" )
    middlename = models.CharField(max_length=25, blank=True, null=True)
    program = models.ForeignKey(Program, on_delete=models.CASCADE ,default=1)

    def __str__(self):
        return f"{self.lastname}, {self.firstname}"


class OrgMember(BaseModel):
    """Model representing a member of an organization."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    date_joined = models.DateField()

    def __str__(self):
        return f"{self.student.firstname}, {self.student.lastname} - {self.organization.name}"


class Boat(models.Model):
    boat_name = models.CharField(max_length=150)
    length = models.DecimalField(max_digits=10, decimal_places=2)
    width = models.DecimalField(max_digits=10, decimal_places=2)
    height = models.DecimalField(max_digits=10, decimal_places=2)
