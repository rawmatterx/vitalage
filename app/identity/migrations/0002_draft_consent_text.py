"""Adds the first DRAFT consent wording, in English and Bengali.

Both are drafts written from research/PILOT_PROTOCOL.md. They are NOT approved
by an ethics committee and the Bengali is an unreviewed draft translation.
Before real participants: the ethics committee approves the English, a native
speaker translates and back-translates the Bengali, and both are added as a
new version (in the admin pages) with is_draft off and ethics_ref filled in.
Text in [square brackets] still has to be filled in.
"""

from django.db import migrations

EN_TITLE = "VitalAge pilot study: information and consent"

EN_SUMMARY = """We are testing whether fitness band data makes a blood-based measure of aging more accurate.
You share a routine blood report, 30 days of fitness band data and one DNA-age test result, now and again after 12 months.
VitalAge is not a diagnosis and does not replace your doctor.
Your name and email are kept apart from your health data. Researchers only see a random code.
You can withdraw at any time in the app. Your research data is then deleted.
Research data is kept for 3 years after the study ends, then deleted."""

EN_TEXT = """What the study is about. VitalAge estimates how fast the body is aging from a routine blood test. This pilot study checks whether adding fitness band data (resting heart rate, steps, sleep and VO2max) makes that estimate track DNA-based aging measures better, and how well it works in Indian adults.

What you will do. You enter the 9 blood markers from a fasting blood report, upload at least 30 days of fitness band data around the blood test, and enter the result of one DNA-age test taken within 30 days of the blood test. You answer a few questions about smoking. After 12 months we ask you to repeat the blood test, band data and DNA test.

Costs. The DNA-age test is a commercial test. [Whether the study pays for it, or you do, will be stated here before you agree.] Routine blood tests are [paid by / reimbursed by: to be completed].

Risks and benefits. There is no physical risk beyond a routine blood draw. Seeing a result that says your body looks older than your age can be worrying; it is an estimate, not a diagnosis, and you should talk to your doctor about any health concern. You will see your own results. The study is not expected to benefit your health directly.

What we collect and why. Your email (to sign you in and contact you), your date of birth (to work out your age; the research data keeps only the year), sex and smoking status, the 9 blood marker values, monthly averages of your band data, your band model, and your DNA-age results. Your lab report file is read on your own phone and is never uploaded. Every date in the research data is turned into a count of days, so the research data holds no calendar dates.

Who can see your data. You can see all of your own data. The study coordinator sees your study code and which steps you have completed, but not your health values. The analyst sees only coded data with no name, email or dates. Nobody else.

Where it is stored. On a secure, encrypted server run by [hosting company and country: to be confirmed with the ethics committee]. Your email and date of birth are stored separately from your health data and are encrypted.

How long it is kept. Research data is kept for 3 years after the study ends and then deleted.

Your rights. Taking part is voluntary. You can download your data, correct it, or withdraw at any time in the app without giving a reason. If you withdraw, your research data is deleted and the link between your account and your study code is removed. Results that were already published from the whole group cannot be changed. You can raise a concern with [grievance contact name and email] and, under India's Digital Personal Data Protection Act 2023, with the Data Protection Board of India.

Contacts. Study coordinator: [name, email]. Ethics committee: [name, approval number, contact]."""

BN_TITLE = "VitalAge পাইলট গবেষণা: তথ্য ও সম্মতি"

BN_SUMMARY = """আমরা পরীক্ষা করছি, রক্ত পরীক্ষা থেকে বার্ধক্য মাপার পদ্ধতিতে ফিটনেস ব্যান্ডের তথ্য যোগ করলে তা আরও নির্ভুল হয় কিনা।
আপনি একটি সাধারণ রক্ত পরীক্ষার রিপোর্ট, ৩০ দিনের ফিটনেস ব্যান্ডের তথ্য এবং একটি DNA-বয়স পরীক্ষার ফল দেবেন, এখন এবং ১২ মাস পরে আবার।
VitalAge কোনো রোগনির্ণয় নয় এবং আপনার ডাক্তারের বিকল্প নয়।
আপনার নাম ও ইমেল আপনার স্বাস্থ্য-তথ্য থেকে আলাদা রাখা হয়। গবেষকরা শুধু একটি এলোমেলো কোড দেখতে পান।
আপনি যেকোনো সময় অ্যাপ থেকে গবেষণা ছেড়ে দিতে পারেন। তখন আপনার গবেষণা-তথ্য মুছে ফেলা হবে।
গবেষণা শেষ হওয়ার পর গবেষণা-তথ্য ৩ বছর রাখা হবে, তারপর মুছে ফেলা হবে।"""

BN_TEXT = """গবেষণাটি কী নিয়ে। VitalAge একটি সাধারণ রক্ত পরীক্ষা থেকে অনুমান করে শরীর কত দ্রুত বুড়িয়ে যাচ্ছে। এই পাইলট গবেষণা দেখবে, ফিটনেস ব্যান্ডের তথ্য (বিশ্রামের সময় হৃদস্পন্দন, পদক্ষেপ, ঘুম এবং VO2max) যোগ করলে সেই অনুমান DNA-ভিত্তিক বার্ধক্য মাপের সঙ্গে আরও ভালোভাবে মেলে কিনা, এবং ভারতীয় প্রাপ্তবয়স্কদের ক্ষেত্রে এটি কতটা কাজ করে।

আপনাকে যা করতে হবে। খালি পেটে করা রক্ত পরীক্ষার রিপোর্ট থেকে ৯টি মান লিখবেন, রক্ত পরীক্ষার আশেপাশের অন্তত ৩০ দিনের ফিটনেস ব্যান্ডের তথ্য আপলোড করবেন, এবং রক্ত পরীক্ষার ৩০ দিনের মধ্যে করা একটি DNA-বয়স পরীক্ষার ফল লিখবেন। ধূমপান নিয়ে কয়েকটি প্রশ্নের উত্তর দেবেন। ১২ মাস পরে আমরা আপনাকে রক্ত পরীক্ষা, ব্যান্ডের তথ্য এবং DNA পরীক্ষা আবার করতে বলব।

খরচ। DNA-বয়স পরীক্ষাটি একটি বাণিজ্যিক পরীক্ষা। [এর খরচ গবেষণা দেবে না আপনি দেবেন, তা আপনি সম্মতি দেওয়ার আগে এখানে লেখা থাকবে।] সাধারণ রক্ত পরীক্ষার খরচ [কে দেবে বা ফেরত দেওয়া হবে কিনা: পূরণ করতে হবে]।

ঝুঁকি ও সুবিধা। সাধারণ রক্ত নেওয়ার বাইরে কোনো শারীরিক ঝুঁকি নেই। যদি ফলাফলে দেখা যায় আপনার শরীর বয়সের চেয়ে বেশি বুড়ো দেখাচ্ছে, তা চিন্তার কারণ হতে পারে; এটি একটি অনুমান, রোগনির্ণয় নয়, এবং স্বাস্থ্য নিয়ে যেকোনো চিন্তার কথা আপনার ডাক্তারের সঙ্গে বলুন। আপনি নিজের ফলাফল দেখতে পাবেন। এই গবেষণা সরাসরি আপনার স্বাস্থ্যের উপকার করবে বলে আশা করা হয় না।

আমরা কী তথ্য নিই এবং কেন। আপনার ইমেল (সাইন ইন ও যোগাযোগের জন্য), জন্মতারিখ (বয়স হিসাব করতে; গবেষণা-তথ্যে শুধু জন্মসাল থাকে), লিঙ্গ ও ধূমপানের অবস্থা, রক্তের ৯টি মান, ব্যান্ডের তথ্যের মাসিক গড়, ব্যান্ডের মডেল এবং DNA-বয়সের ফল। আপনার ল্যাব রিপোর্টের ফাইল আপনার নিজের ফোনেই পড়া হয়, কখনো আপলোড হয় না। গবেষণা-তথ্যে প্রতিটি তারিখকে দিনের সংখ্যায় বদলে দেওয়া হয়, তাই সেখানে কোনো ক্যালেন্ডারের তারিখ থাকে না।

কে আপনার তথ্য দেখতে পারেন। আপনি নিজের সব তথ্য দেখতে পারেন। গবেষণা সমন্বয়ক আপনার গবেষণা-কোড এবং আপনি কোন ধাপগুলো শেষ করেছেন তা দেখেন, কিন্তু আপনার স্বাস্থ্যের মান দেখেন না। বিশ্লেষক শুধু কোড করা তথ্য দেখেন, যাতে নাম, ইমেল বা তারিখ নেই। আর কেউ নয়।

তথ্য কোথায় রাখা হয়। [হোস্টিং সংস্থা ও দেশ: এথিক্স কমিটির সঙ্গে নিশ্চিত করতে হবে] দ্বারা পরিচালিত একটি সুরক্ষিত, এনক্রিপ্ট করা সার্ভারে। আপনার ইমেল ও জন্মতারিখ স্বাস্থ্য-তথ্য থেকে আলাদা এবং এনক্রিপ্ট করে রাখা হয়।

কতদিন রাখা হয়। গবেষণা শেষ হওয়ার পর গবেষণা-তথ্য ৩ বছর রাখা হয়, তারপর মুছে ফেলা হয়।

আপনার অধিকার। অংশগ্রহণ সম্পূর্ণ স্বেচ্ছায়। আপনি যেকোনো সময় কোনো কারণ না দেখিয়ে অ্যাপ থেকে নিজের তথ্য ডাউনলোড করতে, সংশোধন করতে বা গবেষণা ছেড়ে দিতে পারেন। ছেড়ে দিলে আপনার গবেষণা-তথ্য মুছে ফেলা হয় এবং আপনার অ্যাকাউন্ট ও গবেষণা-কোডের সংযোগ সরিয়ে দেওয়া হয়। পুরো দলের তথ্য থেকে যে ফলাফল আগেই প্রকাশিত হয়েছে, তা বদলানো যায় না। কোনো অভিযোগ থাকলে [অভিযোগ গ্রহণকারীর নাম ও ইমেল]-কে জানাতে পারেন, এবং ভারতের ডিজিটাল ব্যক্তিগত তথ্য সুরক্ষা আইন ২০২৩ অনুযায়ী ভারতের ডেটা প্রোটেকশন বোর্ডেও জানাতে পারেন।

যোগাযোগ। গবেষণা সমন্বয়ক: [নাম, ইমেল]। এথিক্স কমিটি: [নাম, অনুমোদন নম্বর, যোগাযোগ]।"""


def add_drafts(apps, schema_editor):
    ConsentVersion = apps.get_model("identity", "ConsentVersion")
    import hashlib
    for lang, title, summary, text in (("en", EN_TITLE, EN_SUMMARY, EN_TEXT),
                                       ("bn", BN_TITLE, BN_SUMMARY, BN_TEXT)):
        ConsentVersion.objects.create(
            version="0.1-draft", language=lang, title=title, summary=summary, text=text,
            text_hash=hashlib.sha256((summary + "\n" + text).encode()).hexdigest(),
            is_draft=True, ethics_ref="")


def remove_drafts(apps, schema_editor):
    apps.get_model("identity", "ConsentVersion").objects.filter(version="0.1-draft").delete()


class Migration(migrations.Migration):
    dependencies = [("identity", "0001_initial")]
    operations = [migrations.RunPython(add_drafts, remove_drafts)]
