"""CMS app constants"""

COURSE_INDEX_SLUG = "courses"
CMS_EDITORS_GROUP_NAME = "Editors"

PROGRAM_INDEX_SLUG = "programs"
PROGRAM_COLLECTION_INDEX_SLUG = "program-collections"
CERTIFICATE_INDEX_SLUG = "certificate"
SIGNATORY_INDEX_SLUG = "signatories"
INSTRUCTOR_INDEX_SLUG = "instructors"

ONE_MINUTE = 60

FEATURED_ITEMS_CACHE_KEY = "CMS_homepage_featured_courses"

HYL_CHOICE_REALWORLD_LEARNING = {
    "icon": "IconConnectedPeople",
    "title": "Real-World Learning",
    "text": "Learn from MIT faculty and experts who ground their teaching in real-world cases rather than mathematical models, making the material approachable for all.",
}
HYL_CHOICE_LEARN_BY_DOING = {
    "icon": "IconBrains",
    "title": "Practical Application",
    "text": "Apply your new knowledge with hands-on, practical exercises drawn from healthcare, sports, finance, sustainability, and more.",
}
HYL_CHOICE_LEARN_FROM_OTHERS = {
    "icon": "IconBrains",
    "title": "Learn From Others",
    "text": "Connect with an international community of professionals working on real-world projects.",
}
HYL_CHOICE_LEARN_ON_DEMAND = {
    "icon": "IconBrains",
    "title": "Learn On Demand",
    "text": "Access all course content online with complete flexibility to study at your own pace.",
}
HYL_CHOICE_AI_ENABLED_SUPPORT = {
    "icon": "IconComputerBulb",
    "title": "AI-Enabled Support",
    "text": "Deepen your understanding of the course material and get help on assignments from AskTIM, the AI assistant built by MIT researchers.",
}
HYL_CHOICE_STACKABLE_CREDENTIALS = {
    "icon": "IconCertificate",
    "title": "Stackable Credentials",
    "text": "Earn an MIT Open Learning certificate at each milestone—module, course, and program—demonstrating your AI expertise. Available in paid courses only.",
}

HYL_CHOICES = {
    "realworld_learning": HYL_CHOICE_REALWORLD_LEARNING,
    "learn_by_doing": HYL_CHOICE_LEARN_BY_DOING,
    "learn_from_others": HYL_CHOICE_LEARN_FROM_OTHERS,
    "learn_on_demand": HYL_CHOICE_LEARN_ON_DEMAND,
    "ai_enabled_support": HYL_CHOICE_AI_ENABLED_SUPPORT,
    "stackable_credentials": HYL_CHOICE_STACKABLE_CREDENTIALS,
}
