"""
DERTOUR Synthetic Data Seeder
Creates demo users for each role with predictable passwords and portfolio data
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import AsyncSessionLocal, init_db
from app.models.user import User, UserRole
from app.models.initiative import Initiative, InitiativeStatus, InitiativePriority
from app.models.milestone import Milestone, MilestoneStatus
from app.models.dependency import Dependency, DependencyType, DependencyStatus
from app.core.security import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Demo user data - one user per role with predictable passwords
DEMO_USERS = [
    {
        "email": "admin@dertour.de",
        "full_name": "System Administrator",
        "role": UserRole.ADMIN,
        "password": "Admin123!",
        "is_active": True,
    },
    {
        "email": "pmo@dertour.de",
        "full_name": "PMO Manager",
        "role": UserRole.PMO_MANAGER,
        "password": "Pmo123!",
        "is_active": True,
    },
    {
        "email": "executive@dertour.de",
        "full_name": "Executive User",
        "role": UserRole.EXECUTIVE,
        "password": "Exec123!",
        "is_active": True,
    },
    {
        "email": "team@dertour.de",
        "full_name": "Team Member",
        "role": UserRole.TEAM_MEMBER,
        "password": "Team123!",
        "is_active": True,
    },
    {
        "email": "viewer@dertour.de",
        "full_name": "View Only User",
        "role": UserRole.TEAM_MEMBER,
        "password": "View123!",
        "is_active": True,
    },
]


# Synthetic initiatives data
SYNTHETIC_INITIATIVES = [
    {
        "title": "Digital Transformation Program",
        "description": "Enterprise-wide digital transformation initiative to modernize legacy systems and adopt cloud-native architecture.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.CRITICAL,
        "start_date": date(2024, 1, 15),
        "target_date": date(2024, 12, 31),
        "budget_allocated": 2500000.0,
        "budget_spent": 850000.0,
        "health_score": 85.0,
    },
    {
        "title": "Customer Experience Platform",
        "description": "Build a unified customer experience platform integrating web, mobile, and in-store touchpoints.",
        "status": InitiativeStatus.AT_RISK,
        "priority": InitiativePriority.HIGH,
        "start_date": date(2024, 2, 1),
        "target_date": date(2024, 10, 30),
        "budget_allocated": 1200000.0,
        "budget_spent": 720000.0,
        "health_score": 62.0,
    },
    {
        "title": "Data Analytics Modernization",
        "description": "Migrate from legacy BI tools to modern cloud-based analytics platform with AI/ML capabilities.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.HIGH,
        "start_date": date(2024, 3, 1),
        "target_date": date(2024, 11, 15),
        "budget_allocated": 800000.0,
        "budget_spent": 320000.0,
        "health_score": 78.0,
    },
    {
        "title": "Supply Chain Optimization",
        "description": "Implement predictive analytics and automation to optimize supply chain operations.",
        "status": InitiativeStatus.BLOCKED,
        "priority": InitiativePriority.HIGH,
        "start_date": date(2024, 1, 1),
        "target_date": date(2024, 9, 30),
        "budget_allocated": 1500000.0,
        "budget_spent": 450000.0,
        "health_score": 45.0,
        "block_reason": "Waiting for vendor contract approval and third-party integration certification.",
    },
    {
        "title": "Mobile App Redesign",
        "description": "Complete redesign of customer mobile application with improved UX and performance.",
        "status": InitiativeStatus.ON_HOLD,
        "priority": InitiativePriority.MEDIUM,
        "start_date": date(2024, 4, 1),
        "target_date": date(2024, 8, 31),
        "budget_allocated": 400000.0,
        "budget_spent": 50000.0,
        "health_score": 50.0,
    },
    {
        "title": "Cybersecurity Enhancement",
        "description": "Strengthen security posture with zero-trust architecture and advanced threat detection.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.CRITICAL,
        "start_date": date(2024, 2, 15),
        "target_date": date(2024, 12, 15),
        "budget_allocated": 1800000.0,
        "budget_spent": 600000.0,
        "health_score": 92.0,
    },
    {
        "title": "HR System Migration",
        "description": "Migrate from legacy HR system to modern cloud-based HRIS with self-service capabilities.",
        "status": InitiativeStatus.COMPLETED,
        "priority": InitiativePriority.MEDIUM,
        "start_date": date(2023, 6, 1),
        "target_date": date(2024, 3, 31),
        "actual_end_date": date(2024, 3, 15),
        "budget_allocated": 600000.0,
        "budget_spent": 580000.0,
        "health_score": 95.0,
    },
    {
        "title": "Finance Process Automation",
        "description": "Automate invoice processing, expense management, and financial reporting workflows.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.HIGH,
        "start_date": date(2024, 3, 15),
        "target_date": date(2024, 10, 31),
        "budget_allocated": 900000.0,
        "budget_spent": 280000.0,
        "health_score": 80.0,
    },
    {
        "title": "Marketing Automation Platform",
        "description": "Implement integrated marketing automation with personalization and campaign management.",
        "status": InitiativeStatus.AT_RISK,
        "priority": InitiativePriority.MEDIUM,
        "start_date": date(2024, 2, 1),
        "target_date": date(2024, 9, 1),
        "budget_allocated": 700000.0,
        "budget_spent": 420000.0,
        "health_score": 55.0,
    },
    {
        "title": "Cloud Infrastructure Migration",
        "description": "Migrate on-premises infrastructure to cloud with containerization and microservices.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.CRITICAL,
        "start_date": date(2024, 1, 1),
        "target_date": date(2024, 12, 31),
        "budget_allocated": 3000000.0,
        "budget_spent": 1200000.0,
        "health_score": 88.0,
    },
    {
        "title": "Employee Collaboration Tools",
        "description": "Deploy modern collaboration suite with integrated communication and document management.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.MEDIUM,
        "start_date": date(2024, 4, 1),
        "target_date": date(2024, 8, 15),
        "budget_allocated": 350000.0,
        "budget_spent": 120000.0,
        "health_score": 75.0,
    },
    {
        "title": "IoT Fleet Management",
        "description": "Implement IoT sensors and analytics for fleet tracking and predictive maintenance.",
        "status": InitiativeStatus.ON_HOLD,
        "priority": InitiativePriority.LOW,
        "start_date": date(2024, 5, 1),
        "target_date": date(2024, 12, 31),
        "budget_allocated": 500000.0,
        "budget_spent": 25000.0,
        "health_score": 40.0,
    },
    {
        "title": "E-commerce Platform Upgrade",
        "description": "Upgrade e-commerce platform with improved checkout, recommendations, and payment options.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.HIGH,
        "start_date": date(2024, 3, 1),
        "target_date": date(2024, 11, 30),
        "budget_allocated": 1100000.0,
        "budget_spent": 440000.0,
        "health_score": 82.0,
    },
    {
        "title": "Document Management System",
        "description": "Implement enterprise document management with OCR, search, and workflow automation.",
        "status": InitiativeStatus.AT_RISK,
        "priority": InitiativePriority.MEDIUM,
        "start_date": date(2024, 2, 15),
        "target_date": date(2024, 8, 31),
        "budget_allocated": 450000.0,
        "budget_spent": 315000.0,
        "health_score": 58.0,
    },
    {
        "title": "AI Customer Service Bot",
        "description": "Deploy AI-powered chatbot for customer service with natural language processing.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.HIGH,
        "start_date": date(2024, 4, 15),
        "target_date": date(2024, 10, 15),
        "budget_allocated": 600000.0,
        "budget_spent": 180000.0,
        "health_score": 77.0,
    },
    {
        "title": "Legacy System Decommission",
        "description": "Retire and migrate data from legacy systems no longer supported by vendors.",
        "status": InitiativeStatus.BLOCKED,
        "priority": InitiativePriority.HIGH,
        "start_date": date(2024, 1, 15),
        "target_date": date(2024, 7, 31),
        "budget_allocated": 750000.0,
        "budget_spent": 225000.0,
        "health_score": 35.0,
        "block_reason": "Data migration validation failed - requires additional security review.",
    },
    {
        "title": "API Gateway Implementation",
        "description": "Centralize API management with gateway, rate limiting, and developer portal.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.HIGH,
        "start_date": date(2024, 3, 1),
        "target_date": date(2024, 9, 30),
        "budget_allocated": 550000.0,
        "budget_spent": 220000.0,
        "health_score": 83.0,
    },
    {
        "title": "DevOps Toolchain Modernization",
        "description": "Implement CI/CD pipelines, infrastructure as code, and observability stack.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.CRITICAL,
        "start_date": date(2024, 2, 1),
        "target_date": date(2024, 8, 31),
        "budget_allocated": 650000.0,
        "budget_spent": 325000.0,
        "health_score": 90.0,
    },
    {
        "title": "Customer Data Platform",
        "description": "Unify customer data from multiple sources into single customer view.",
        "status": InitiativeStatus.AT_RISK,
        "priority": InitiativePriority.CRITICAL,
        "start_date": date(2024, 1, 1),
        "target_date": date(2024, 12, 31),
        "budget_allocated": 1400000.0,
        "budget_spent": 560000.0,
        "health_score": 60.0,
    },
    {
        "title": "Sustainability Tracking System",
        "description": "Implement carbon footprint tracking and sustainability reporting platform.",
        "status": InitiativeStatus.ON_TRACK,
        "priority": InitiativePriority.LOW,
        "start_date": date(2024, 5, 1),
        "target_date": date(2024, 11, 30),
        "budget_allocated": 300000.0,
        "budget_spent": 60000.0,
        "health_score": 72.0,
    },
]


def generate_milestones_for_initiative(initiative_id: str, initiative_data: dict) -> List[dict]:
    """Generate realistic milestones for an initiative."""
    start_date = initiative_data["start_date"]
    target_date = initiative_data["target_date"]
    duration_days = (target_date - start_date).days
    
    milestones = []
    milestone_templates = [
        ("Project Kickoff", "Official project start and team onboarding", 0.05),
        ("Requirements Complete", "All business requirements documented and approved", 0.15),
        ("Design Review", "Technical and UX design review completed", 0.25),
        ("Development Sprint 1", "First major development milestone", 0.35),
        ("Mid-Project Review", "50% completion checkpoint", 0.50),
        ("Integration Testing", "System integration testing complete", 0.65),
        ("User Acceptance Testing", "UAT sign-off from stakeholders", 0.80),
        ("Production Deployment", "Go-live in production environment", 0.90),
        ("Project Closure", "Final documentation and handover", 0.95),
    ]
    
    for i, (title, desc, progress) in enumerate(milestone_templates):
        due_date = start_date + timedelta(days=int(duration_days * progress))
        
        # Determine status based on initiative status and due date
        if initiative_data["status"] == InitiativeStatus.COMPLETED:
            status = MilestoneStatus.COMPLETED
            completed_date = due_date
        elif due_date < date.today():
            if initiative_data["status"] in [InitiativeStatus.AT_RISK, InitiativeStatus.BLOCKED]:
                status = MilestoneStatus.MISSED
                completed_date = None
            else:
                status = MilestoneStatus.COMPLETED
                completed_date = due_date
        elif due_date < date.today() + timedelta(days=30):
            status = MilestoneStatus.IN_PROGRESS
            completed_date = None
        else:
            status = MilestoneStatus.PLANNED
            completed_date = None
        
        milestones.append({
            "title": title,
            "description": desc,
            "status": status,
            "due_date": due_date,
            "completed_date": completed_date,
            "sequence_order": i,
            "is_critical_path": i in [0, 4, 7, 8],  # Key milestones on critical path
        })
    
    return milestones


def generate_dependencies() -> List[tuple]:
    """Generate dependency relationships between initiatives."""
    # (source_index, target_index, dependency_type, description)
    return [
        # Digital Transformation depends on Cloud Infrastructure
        (0, 9, DependencyType.DEPENDS_ON, "Digital transformation requires cloud infrastructure foundation"),
        # Customer Experience depends on Data Analytics
        (1, 2, DependencyType.DEPENDS_ON, "Customer platform requires analytics capabilities"),
        # Supply Chain depends on Cloud Infrastructure
        (3, 9, DependencyType.DEPENDS_ON, "Supply chain optimization needs cloud infrastructure"),
        # Mobile App depends on Customer Experience Platform
        (4, 1, DependencyType.DEPENDS_ON, "Mobile app redesign requires customer platform foundation"),
        # Cybersecurity Enhancement blocks Legacy System Decommission
        (5, 15, DependencyType.BLOCKS, "Security review required before legacy decommission"),
        # HR System Migration enables Finance Process Automation
        (6, 7, DependencyType.BLOCKS, "HR system data needed for finance automation"),
        # Finance Process Automation relates to Marketing Automation
        (7, 8, DependencyType.RELATES_TO, "Finance and marketing automation are related initiatives"),
        # Cloud Infrastructure blocks Supply Chain Optimization
        (9, 3, DependencyType.BLOCKS, "Cloud infrastructure must be ready for supply chain"),
        # Employee Collaboration Tools depends on Cloud Infrastructure
        (10, 9, DependencyType.DEPENDS_ON, "Collaboration tools need cloud foundation"),
        # IoT Fleet Management depends on Cloud Infrastructure
        (11, 9, DependencyType.DEPENDS_ON, "IoT platform requires cloud infrastructure"),
        # E-commerce Platform Upgrade depends on Customer Experience Platform
        (12, 1, DependencyType.DEPENDS_ON, "E-commerce upgrade requires customer platform"),
        # Document Management System depends on Cloud Infrastructure
        (13, 9, DependencyType.DEPENDS_ON, "Document management needs cloud storage"),
        # AI Customer Service Bot depends on Customer Data Platform
        (14, 18, DependencyType.DEPENDS_ON, "AI bot requires unified customer data"),
        # Legacy System Decommission depends on Data Analytics Modernization
        (15, 2, DependencyType.DEPENDS_ON, "Analytics migration must complete before decommission"),
        # API Gateway Implementation blocks Digital Transformation
        (16, 0, DependencyType.BLOCKS, "API gateway must be ready for digital transformation"),
        # DevOps Toolchain Modernization enables Cloud Infrastructure Migration
        (17, 9, DependencyType.BLOCKS, "DevOps toolchain required for cloud migration"),
        # Customer Data Platform depends on Data Analytics Modernization
        (18, 2, DependencyType.DEPENDS_ON, "Customer data platform requires analytics foundation"),
        # Sustainability Tracking System depends on Data Analytics Modernization
        (19, 2, DependencyType.DEPENDS_ON, "Sustainability tracking needs analytics platform"),
        # Additional cross-dependencies
        (0, 16, DependencyType.DEPENDS_ON, "Digital transformation requires API gateway"),
        (1, 18, DependencyType.DEPENDS_ON, "Customer experience requires customer data platform"),
        (8, 18, DependencyType.DEPENDS_ON, "Marketing automation requires customer data platform"),
    ]


async def seed_users(db: AsyncSession) -> List[User]:
    """Create demo users for each role."""
    logger.info("Seeding users...")
    
    users = []
    for user_data in DEMO_USERS:
        # Check if user already exists
        result = await db.execute(
            select(User).where(User.email == user_data["email"])
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"User '{user_data['email']}' already exists, skipping...")
            users.append(existing)
            continue
        
        # Create new user
        user = User(
            id=str(uuid4()),
            email=user_data["email"],
            full_name=user_data["full_name"],
            role=user_data["role"],
            hashed_password=get_password_hash(user_data["password"]),
            is_active=user_data["is_active"],
        )
        db.add(user)
        users.append(user)
        logger.info(f"Created user: {user.email} ({user.role.value})")
    
    await db.commit()
    logger.info(f"Seeded {len(users)} users")
    return users


async def seed_initiatives(db: AsyncSession, users: List[User]) -> List[Initiative]:
    """Create synthetic initiatives."""
    logger.info("Seeding initiatives...")
    
    # Get PMO and EXECUTIVE users for ownership
    pmo_users = [u for u in users if u.role == UserRole.PMO_MANAGER]
    exec_users = [u for u in users if u.role == UserRole.EXECUTIVE]
    all_users = users
    
    initiatives = []
    for i, init_data in enumerate(SYNTHETIC_INITIATIVES):
        # Check if initiative with same title already exists
        result = await db.execute(
            select(Initiative).where(Initiative.title == init_data["title"])
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"Initiative '{init_data['title']}' already exists, skipping...")
            initiatives.append(existing)
            continue
        
        # Assign owner based on priority
        if init_data["priority"] == InitiativePriority.CRITICAL and exec_users:
            owner = exec_users[i % len(exec_users)]
        elif pmo_users:
            owner = pmo_users[i % len(pmo_users)]
        else:
            owner = all_users[i % len(all_users)]
        
        # Create initiative
        initiative = Initiative(
            id=str(uuid4()),
            title=init_data["title"],
            description=init_data["description"],
            status=init_data["status"],
            priority=init_data["priority"],
            owner_id=owner.id,
            start_date=init_data["start_date"],
            target_date=init_data["target_date"],
            actual_end_date=init_data.get("actual_end_date"),
            health_score=init_data.get("health_score"),
            budget_allocated=init_data.get("budget_allocated", 0.0),
            budget_spent=init_data.get("budget_spent", 0.0),
            block_reason=init_data.get("block_reason"),
            created_by=owner.id,
            updated_by=owner.id,
        )
        db.add(initiative)
        initiatives.append(initiative)
        logger.info(f"Created initiative: {initiative.title}")
    
    await db.commit()
    logger.info(f"Seeded {len(initiatives)} initiatives")
    return initiatives


async def seed_milestones(db: AsyncSession, initiatives: List[Initiative]) -> List[Milestone]:
    """Create milestones for each initiative."""
    logger.info("Seeding milestones...")
    
    all_milestones = []
    
    for initiative in initiatives:
        # Find the original data for this initiative by matching title
        init_data = None
        initiative_title = initiative.title
        for data in SYNTHETIC_INITIATIVES:
            if data["title"] == initiative_title:
                init_data = data
                break
        
        if not init_data:
            continue
        
        # Check if milestones already exist for this initiative
        result = await db.execute(
            select(Milestone).where(Milestone.initiative_id == initiative.id)
        )
        existing = result.scalars().all()
        
        if existing:
            logger.info(f"Milestones already exist for '{initiative_title}', skipping...")
            all_milestones.extend(existing)
            continue
        
        # Generate milestones
        milestone_data_list = generate_milestones_for_initiative(
            initiative.id, init_data
        )
        
        for milestone_data in milestone_data_list:
            milestone = Milestone(
                id=str(uuid4()),
                initiative_id=initiative.id,
                title=milestone_data["title"],
                description=milestone_data["description"],
                status=milestone_data["status"],
                due_date=milestone_data["due_date"],
                completed_date=milestone_data["completed_date"],
                sequence_order=milestone_data["sequence_order"],
                is_critical_path=milestone_data["is_critical_path"],
                created_by=initiative.owner_id,
                updated_by=initiative.owner_id,
            )
            db.add(milestone)
            all_milestones.append(milestone)
        
        logger.info(f"Created {len(milestone_data_list)} milestones for '{initiative_title}'")
    
    await db.commit()
    logger.info(f"Seeded {len(all_milestones)} total milestones")
    return all_milestones


async def seed_dependencies(db: AsyncSession, initiatives: List[Initiative]) -> List[Dependency]:
    """Create dependencies between initiatives."""
    logger.info("Seeding dependencies...")
    
    dependencies = []
    dependency_specs = generate_dependencies()
    
    for source_idx, target_idx, dep_type, description in dependency_specs:
        if source_idx >= len(initiatives) or target_idx >= len(initiatives):
            continue
        
        source_initiative = initiatives[source_idx]
        target_initiative = initiatives[target_idx]
        
        # Check if dependency already exists
        result = await db.execute(
            select(Dependency).where(
                (Dependency.source_initiative_id == source_initiative.id) &
                (Dependency.target_initiative_id == target_initiative.id)
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            source_title = source_initiative.title
            target_title = target_initiative.title
            logger.info(f"Dependency already exists between '{source_title}' and '{target_title}', skipping...")
            dependencies.append(existing)
            continue
        
        # Determine status based on source initiative status
        if source_initiative.status == InitiativeStatus.COMPLETED:
            status = DependencyStatus.RESOLVED
        elif source_initiative.status == InitiativeStatus.BLOCKED:
            status = DependencyStatus.BLOCKED
        elif source_initiative.status == InitiativeStatus.ON_HOLD:
            status = DependencyStatus.PENDING
        else:
            status = DependencyStatus.ACTIVE
        
        # Create dependency
        dependency = Dependency(
            id=str(uuid4()),
            source_initiative_id=source_initiative.id,
            target_initiative_id=target_initiative.id,
            dependency_type=dep_type,
            status=status,
            description=description,
            created_by=source_initiative.owner_id,
        )
        db.add(dependency)
        dependencies.append(dependency)
        
        source_title = source_initiative.title
        target_title = target_initiative.title
        logger.info(f"Created dependency: '{source_title}' -> '{target_title}' ({dep_type.value})")
    
    await db.commit()
    logger.info(f"Seeded {len(dependencies)} dependencies")
    return dependencies


async def clear_portfolio_data(db: AsyncSession):
    """Clear all portfolio data (dependencies, milestones, initiatives)."""
    logger.info("Clearing portfolio data...")
    
    # Delete in order to respect foreign key constraints
    await db.execute(delete(Dependency))
    await db.execute(delete(Milestone))
    await db.execute(delete(Initiative))
    
    await db.commit()
    logger.info("Portfolio data cleared")


async def clear_users(db: AsyncSession):
    """Clear all users except system users."""
    logger.info("Clearing users...")
    
    await db.execute(delete(User))
    await db.commit()
    logger.info("Users cleared")


async def seed_all_data():
    """Seed all synthetic data."""
    logger.info("Starting synthetic data seeding...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Seed users first
            users = await seed_users(db)
            
            # Seed initiatives
            initiatives = await seed_initiatives(db, users)
            
            # Seed milestones
            await seed_milestones(db, initiatives)
            
            # Seed dependencies
            await seed_dependencies(db, initiatives)
            
            logger.info("Synthetic data seeding completed successfully!")
            
        except Exception as e:
            logger.error(f"Error seeding data: {e}")
            await db.rollback()
            raise


async def reset_demo_data():
    """Reset all data and reseed."""
    logger.info("Resetting demo data...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Clear existing data
            await clear_portfolio_data(db)
            await clear_users(db)
            
            # Reseed
            await seed_all_data()
            
            logger.info("Demo data reset completed!")
            
        except Exception as e:
            logger.error(f"Error resetting demo data: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    # Run the seeder
    asyncio.run(seed_all_data())
