"""Build Badge 3 (Data Application Builders Workshop, DABW) lesson notebooks for Snowflake Workspaces.
Usage: python3 build_badge3_notebooks.py
Output: ../notebooks/badge3_dabw/  (11 lesson notebooks, dora/account_setup, dora/dora_setup, dora/dora_tests, data/)

Course code is read verbatim from the Rise export. In lesson notebooks only role and warehouse
names are swapped:  ACCOUNTADMIN -> {{ADMIN_ROLE}}   SYSADMIN -> {{SYSADMIN_ROLE}}   COMPUTE_WH -> {{WAREHOUSE}}
Code the course shows only in screenshots (the Streamlit apps, UI wizards) is transcribed and labelled.
DORA code is never altered.
"""
import base64, html, json, os, re, shutil, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSE = os.path.join(ROOT, "badges", "badge-3-data-application-builders-workshop")
OUT = os.path.join(ROOT, "notebooks", "badge3_dabw")

ADMIN_ROLE, SYSADMIN_ROLE, WAREHOUSE = "BADGE3_DABW_ADMIN", "BADGE3_DABW_ROLE", "BADGE3_DABW_WH"
DOWNLOADS = "@UTIL_DB.PUBLIC.BADGE3_DOWNLOADS"
SETUP_NB, DORA_SETUP_NB, DORA_NB = "dora/account_setup", "dora/dora_setup", "dora/dora_tests"
DATA_FILES = {"fruits_available_for_smoothies.txt": "fruits_available_for_smoot.txt"}

_raw = open(os.path.join(COURSE, "runtime-data.js")).read()
_course = json.loads(base64.b64decode(re.search(r'__jsonp\("runtime-data.js","(.*)"\)', _raw, re.S).group(1)))["course"]
CODE = {}
for _l in _course["lessons"]:
    _codes = [html.unescape(x.get("code") or "").replace("\r\n", "\n").strip("\n")
              for it in _l.get("items") or [] if it.get("type") == "multimedia" and it.get("variant") == "code"
              for x in it["items"]]
    if _codes:
        CODE[html.unescape(re.sub(r"<[^>]+>", "", _l["title"])).strip()] = _codes


def code(page, i=0):
    hits = [k for k in CODE if page in k]
    assert len(hits) == 1, (page, hits)
    return CODE[hits[0]][i]


def isolate(sql):
    sql = re.sub(r"\bACCOUNTADMIN\b", "{{ADMIN_ROLE}}", sql, flags=re.I)
    sql = re.sub(r"\bSYSADMIN\b", "{{SYSADMIN_ROLE}}", sql, flags=re.I)
    return re.sub(r"\bCOMPUTE_WH\b", "{{WAREHOUSE}}", sql, flags=re.I)


def dora_local(sql):
    return re.sub(r"select\s+GRADER\(step, \(actual = expected\), actual, expected, description\)\s+as\s+graded_results\s+from",
                  "select step, actual, expected, (actual = expected) as passed, description from", sql, flags=re.I)


def protected(sql_text):
    """Run course code as given, but report instead of stopping if it errors (the course expects an error here)."""
    body = ("begin\n  execute immediate '" + sql_text.strip().rstrip(";").replace("'", "''") +
            "';\n  return 'ran without error';\nexception when other then\n  return 'Error (as the course predicts): ' || sqlerrm;\nend;")
    return "execute immediate '" + body.replace("'", "''") + "';"


def _id():
    return uuid.uuid4().hex[:8]


def md(text):
    return {"cell_type": "markdown", "id": _id(), "metadata": {}, "source": text.strip("\n")}


def sql(name, text):
    return {"cell_type": "code", "id": _id(), "execution_count": None, "outputs": [],
            "metadata": {"language": "sql", "name": name}, "source": f"%%sql -r {name}\n" + text.strip("\n")}


def py(name, text):
    return {"cell_type": "code", "id": _id(), "execution_count": None, "outputs": [],
            "metadata": {"language": "python", "name": name}, "source": text.strip("\n")}


def course(text):
    return md("> **Course:** " + text.strip().replace("\n", "\n> "))


def note(text):
    return md("> ⚠️ **Note:** " + text.strip().replace("\n", "\n> "))


def story(*titles):
    return md("Story / knowledge-check pages, nothing to run: " + "; ".join(titles) + ".")


def page(title):
    return md(f"## Page: {title}")


def dora(step, what):
    return md(f"### 🤖 DORA check {step} goes here\nThe course has the learner run **{step}** ({what}) at this point.\n"
              f"It is in `{DORA_NB}.ipynb`, section **{step}**, as a local check plus the exact DORA code.")


PREAMBLE_VARS = '''# Isolation mapping (set once per notebook; SQL cells use these via {{...}})
ADMIN_ROLE    = "@@ADMIN@@"   # stands in for the course's ACCOUNTADMIN
SYSADMIN_ROLE = "@@SYS@@"    # stands in for the course's SYSADMIN
WAREHOUSE     = "@@WH@@"      # stands in for the course's COMPUTE_WH
import ast, io
from snowflake.snowpark.context import get_active_session

CUSTOM = 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'
PENDING = 'SMOOTHIES.PUBLIC."Pending Smoothie Orders"'


def pdf(result):
    """A SQL cell's result as pandas (runtime 2.6+ returns a Snowpark DataFrame)."""
    return result.to_pandas() if hasattr(result, "to_pandas") else result


def write_app(app, app_code):
    """SQL equivalent of editing the app in Snowsight's Streamlit editor: write streamlit_app.py into the app's live version."""
    ast.parse(app_code)  # the code must at least be valid Python
    path = f"snow://streamlit/{app}/versions/live/streamlit_app.py"
    get_active_session().file.put_stream(io.BytesIO(app_code.encode()), path, auto_compress=False, overwrite=True)
    print(f"wrote {len(app_code.splitlines())} lines to {path}")'''.replace("@@ADMIN@@", ADMIN_ROLE).replace("@@SYS@@", SYSADMIN_ROLE).replace("@@WH@@", WAREHOUSE)


def preamble(title, purpose):
    ctx = "use role {{SYSADMIN_ROLE}};\nuse secondary roles none;\nuse warehouse {{WAREHOUSE}};\n"
    return [
        md(f"# Badge 3: Data Application Builders Workshop: {title}\n\n{purpose}\n\n"
           "**How to read this notebook**\n"
           "- Each `## Page:` heading is one page of the Rise lesson, in course order.\n"
           "- `> Course:` cells quote what the learner is told to do (text or screenshot steps).\n"
           "- Code cells run that task. Course code is verbatim except role/warehouse names, swapped for "
           f"`{ADMIN_ROLE}` (ACCOUNTADMIN), `{SYSADMIN_ROLE}` (SYSADMIN) and `{WAREHOUSE}` (COMPUTE_WH).\n"
           "- **SQL equivalent** replaces a UI-only step; **From screenshot** marks code the course shows only as an image; "
           "**Derived solution** marks challenge answers the course does not give.\n"
           f"- DORA checks are not run here; see `{DORA_NB}.ipynb`.\n\nPrerequisite: run `{SETUP_NB}.ipynb` once."),
        py("isolation_vars", PREAMBLE_VARS),
        sql("session_context", ctx + "select current_role(), current_warehouse(), current_database(), current_schema();"),
    ]


def app_cell(name, app_var, app_code):
    assert "'''" not in app_code, name
    return py(name, f"write_app({app_var}, r'''{app_code}''')")


def run_app(name, app_fq):
    return sql(name, f"-- SQL equivalent of clicking Run (a Streamlit app run shows up as an EXECUTE STREAMLIT query)\n"
                     f"execute streamlit {app_fq}();")


# ------------------------------------------------------------------ Streamlit app code (from screenshots)
IMPORTS = '''# Import python packages
import streamlit as st
from snowflake.snowpark.context import get_active_session
'''
IMPORTS_COL = IMPORTS + "from snowflake.snowpark.functions import col\n"
TITLE = '''
# Write directly to the app
st.title(":cup_with_straw: Customize Your Smoothie! :cup_with_straw:")
st.write(
    """Choose the fruits you want in your custom Smoothie!
    """)
'''
A1 = IMPORTS + TITLE
A2A = A1 + '''
import streamlit as st

option = st.selectbox(
    'How would you like to be contacted?',
    ('Email', 'Home phone', 'Mobile phone'))

st.write('You selected:', option)
'''
A2B = A1 + '''
option = st.selectbox(
    'What is your favorite fruit?',
    ('Banana', 'Strawberries', 'Peaches'))

st.write('Your favorite fruit is:', option)
'''
A2C = A2B + '''
session = get_active_session()
my_dataframe = session.table("smoothies.public.fruit_options")
st.dataframe(data=my_dataframe, use_container_width=True)
'''
A3A = IMPORTS + TITLE + '''
from snowflake.snowpark.functions import col

session = get_active_session()
my_dataframe = session.table("smoothies.public.fruit_options").select(col('FRUIT_NAME'))
st.dataframe(data=my_dataframe, use_container_width=True)
'''
A3B_BASE = IMPORTS + TITLE + '''
from snowflake.snowpark.functions import col

session = get_active_session()
my_dataframe = session.table("smoothies.public.fruit_options").select(col('FRUIT_NAME'))
#st.dataframe(data=my_dataframe, use_container_width=True)

ingredients_list = st.multiselect(
    'Choose up to 5 ingredients:'
    , my_dataframe
    )
'''
A3B = A3B_BASE
A3B2 = A3B_BASE + '''
st.write(ingredients_list)
st.text(ingredients_list)
'''
A3C = A3B_BASE + '''
if ingredients_list:
    st.write(ingredients_list)
    st.text(ingredients_list)
'''
A3D = A3B_BASE + '''
if ingredients_list:
    st.write(ingredients_list)
    st.text(ingredients_list)

    ingredients_string = ''
'''
A3E = A3B_BASE + '''
if ingredients_list:
    st.write(ingredients_list)
    st.text(ingredients_list)

    ingredients_string = ''

    for fruit_chosen in ingredients_list:
        ingredients_string += fruit_chosen
'''
A3F = A3E + '''
    st.write(ingredients_string)
'''
A3G = A3B_BASE + '''
if ingredients_list:
    ingredients_string = ''

    for fruit_chosen in ingredients_list:
        ingredients_string += fruit_chosen + ' '

    st.write(ingredients_string)


    my_insert_stmt = """ insert into smoothies.public.orders(ingredients)
            values ('""" + ingredients_string + """')"""

    st.write(my_insert_stmt)
'''
A3H = A3B_BASE + '''
if ingredients_list:
    ingredients_string = ''

    for fruit_chosen in ingredients_list:
        ingredients_string += fruit_chosen + ' '

    #st.write(ingredients_string)


    my_insert_stmt = """ insert into smoothies.public.orders(ingredients)
            values ('""" + ingredients_string + """')"""

    #st.write(my_insert_stmt)
    if ingredients_string:
        session.sql(my_insert_stmt).collect()

        st.success('Your Smoothie is ordered!', icon="✅")
'''
A3I = A3B_BASE + '''
if ingredients_list:
    ingredients_string = ''

    for fruit_chosen in ingredients_list:
        ingredients_string += fruit_chosen + ' '

    #st.write(ingredients_string)


    my_insert_stmt = """ insert into smoothies.public.orders(ingredients)
            values ('""" + ingredients_string + """')"""

    #st.write(my_insert_stmt)
    time_to_insert = st.button('Submit Order')

    if time_to_insert:
        session.sql(my_insert_stmt).collect()

        st.success('Your Smoothie is ordered!', icon="✅")
'''
# Lesson 5: col import moves to the top, a name box is added, the name is written to the table
HEAD5 = IMPORTS_COL + TITLE
NAME_BOX = '''
name_on_order = st.text_input('Name on Smoothie:')
st.write('The name on your Smoothie will be:', name_on_order)
'''
BODY5_PRE = '''
session = get_active_session()
my_dataframe = session.table("smoothies.public.fruit_options").select(col('FRUIT_NAME'))
#st.dataframe(data=my_dataframe, use_container_width=True)

ingredients_list = st.multiselect(
    'Choose up to 5 ingredients:'
    , my_dataframe
    )
'''
A5A = HEAD5 + BODY5_PRE
A5B = HEAD5 + NAME_BOX + BODY5_PRE + '''
if ingredients_list:
    ingredients_string = ''

    for fruit_chosen in ingredients_list:
        ingredients_string += fruit_chosen + ' '

    #st.write(ingredients_string)


    my_insert_stmt = """ insert into smoothies.public.orders(ingredients)
            values ('""" + ingredients_string + """')"""

    #st.write(my_insert_stmt)
    time_to_insert = st.button('Submit Order')

    if time_to_insert:
        session.sql(my_insert_stmt).collect()

        st.success('Your Smoothie is ordered!', icon="✅")
'''
A5C = HEAD5 + NAME_BOX + BODY5_PRE + '''
if ingredients_list:
    ingredients_string = ''

    for fruit_chosen in ingredients_list:
        ingredients_string += fruit_chosen + ' '

    #st.write(ingredients_string)


    my_insert_stmt = """ insert into smoothies.public.orders(ingredients, name_on_order)
            values ('""" + ingredients_string + """','"""+name_on_order+ """')"""

    st.write(my_insert_stmt)
    st.stop()

    time_to_insert = st.button('Submit Order')

    if time_to_insert:
        session.sql(my_insert_stmt).collect()

        st.success('Your Smoothie is ordered!', icon="✅")
'''
A5D = HEAD5 + NAME_BOX + BODY5_PRE + '''
if ingredients_list:
    ingredients_string = ''

    for fruit_chosen in ingredients_list:
        ingredients_string += fruit_chosen + ' '

    #st.write(ingredients_string)


    my_insert_stmt = """ insert into smoothies.public.orders(ingredients, name_on_order)
            values ('""" + ingredients_string + """','"""+name_on_order+ """')"""

    # st.write(my_insert_stmt)
    # st.stop()

    time_to_insert = st.button('Submit Order')

    if time_to_insert:
        session.sql(my_insert_stmt).collect()

        st.success(f'Your Smoothie is ordered, {name_on_order}!', icon="✅")
'''
A6 = A5D.replace("    , my_dataframe\n    )", "    , my_dataframe\n    , max_selections=5\n    )")
assert A6 != A5D

# Pending Smoothie Orders
P_HEAD = '''# Import python packages
import streamlit as st
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col, when_matched
'''
P1 = '''# Import python packages
import streamlit as st
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col

# Write directly to the app
st.title(":cup_with_straw: Pending Smoothie Orders! :cup_with_straw:")
st.write(
    """Orders that need to be filled.
    """
)

session = get_active_session()
my_dataframe = session.table("smoothies.public.orders") \\
    .filter(col("ORDER_FILLED") == 0) \\
    .collect()
editable_df = st.data_editor(my_dataframe)
'''
P2 = P_HEAD + '''
# Write directly to the app
st.title(":cup_with_straw: Pending Smoothie Orders :cup_with_straw:")
st.write("Orders that need to be filled.")

session = get_active_session()
my_dataframe = session.table("smoothies.public.orders") \\
    .filter(col("ORDER_FILLED") == 0) \\
    .collect()
editable_df = st.data_editor(my_dataframe)

submitted = st.button('Submit')

if submitted:
    st.success("Someone clicked the button.", icon="👍")
'''
P3 = P_HEAD + '''
# Write directly to the app
st.title(":cup_with_straw: Pending Smoothie Orders :cup_with_straw:")
st.write("Orders that need to be filled.")

session = get_active_session()
my_dataframe = session.table("smoothies.public.orders") \\
    .filter(col("ORDER_FILLED") == 0) \\
    .collect()
editable_df = st.data_editor(my_dataframe)

submitted = st.button('Submit')

if submitted:
    st.success("Someone clicked the button.", icon="👍")

    og_dataset = session.table("smoothies.public.orders")
    edited_dataset = session.create_dataframe(editable_df)
    og_dataset.merge(edited_dataset
                     , (og_dataset['ORDER_UID'] == edited_dataset['ORDER_UID'])
                     , [when_matched().update({'ORDER_FILLED': edited_dataset['ORDER_FILLED']})]
                    )
'''
P4 = P_HEAD + '''
# Write directly to the app
st.title(":cup_with_straw: Pending Smoothie Orders :cup_with_straw:")
st.write("""Orders that need to filled.""")

session = get_active_session()
my_dataframe = session.table("smoothies.public.orders") \\
    .filter(col("ORDER_FILLED") == 0) \\
    .collect()

if my_dataframe:
    editable_df = st.data_editor(my_dataframe)
    submitted = st.button('Submit')
    if submitted:

        og_dataset = session.table("smoothies.public.orders")
        edited_dataset = session.create_dataframe(editable_df)

        try:
            og_dataset.merge(edited_dataset
                             , (og_dataset['ORDER_UID'] == edited_dataset['ORDER_UID'])
                             , [when_matched().update({'ORDER_FILLED': edited_dataset['ORDER_FILLED']})]
                            )
            st.success("Order(s) Updated!", icon="👍")
        except:
            st.write('Something went wrong.')
else:
    st.success('There are no pending orders right now', icon="👍")
'''

# ------------------------------------------------------------------ account setup / dora setup
NB = {}
NB[SETUP_NB] = [
    md("# Badge 3: account setup\n\nRun once, before Lesson 1. The course lab is a Snowflake trial account where the learner has "
       "ACCOUNTADMIN, SYSADMIN and the warehouse COMPUTE_WH. This account is shared, so these cells create stand-ins:\n\n"
       f"| Course | Here |\n|---|---|\n| ACCOUNTADMIN | `{ADMIN_ROLE}` |\n| SYSADMIN | `{SYSADMIN_ROLE}` |\n| COMPUTE_WH | `{WAREHOUSE}` |\n\n"
       "Account-level steps the course does as ACCOUNTADMIN (resource monitor, DORA setup) run as the real ACCOUNTADMIN and are labelled. "
       "Object names (SMOOTHIES, FRUIT_OPTIONS, ORDERS, the two apps, UTIL_DB functions) are the course's."),
    py("isolation_vars", PREAMBLE_VARS),
    md("## Check for name collisions\nCourse database names are account-wide."),
    sql("existing_course_objects", "use role accountadmin;\nshow databases like 'SMOOTHIES';"),
    md("## Roles and grants"),
    sql("create_roles", """use role accountadmin;
create role if not exists {{ADMIN_ROLE}} comment = 'Badge 3 stand-in for ACCOUNTADMIN';
create role if not exists {{SYSADMIN_ROLE}} comment = 'Badge 3 stand-in for SYSADMIN';
grant role {{SYSADMIN_ROLE}} to role {{ADMIN_ROLE}};
grant role {{ADMIN_ROLE}} to role sysadmin;
set badge_user = current_user();
grant role {{ADMIN_ROLE}} to user identifier($badge_user);
grant role {{SYSADMIN_ROLE}} to user identifier($badge_user);
-- SYSADMIN creates the SMOOTHIES database (Lesson 2)
grant create database on account to role {{SYSADMIN_ROLE}};
-- ACCOUNTADMIN can read SNOWFLAKE.ACCOUNT_USAGE (DABW005 reads query_history)
grant imported privileges on database snowflake to role {{ADMIN_ROLE}};"""),
    md("## Warehouse (stands in for COMPUTE_WH; the Lesson 2 checklist says SYSADMIN owns it)"),
    sql("create_warehouse", """use role accountadmin;
create warehouse if not exists {{WAREHOUSE}}
  warehouse_size = xsmall auto_suspend = 60 auto_resume = true initially_suspended = true
  comment = 'Badge 3 stand-in for COMPUTE_WH';
grant ownership on warehouse {{WAREHOUSE}} to role {{SYSADMIN_ROLE}} copy current grants;"""),
    md("## UTIL_DB (shared across badges; home of the DORA GRADER and, in Lesson 8, the course's functions)"),
    sql("util_db_grants", """use role accountadmin;
create database if not exists UTIL_DB comment = 'Shared utility database for badge course audits (DORA grader, course stages)';
grant ownership on database UTIL_DB to role sysadmin copy current grants;
grant ownership on schema UTIL_DB.PUBLIC to role sysadmin copy current grants;
grant usage on database UTIL_DB to role {{ADMIN_ROLE}};
grant usage on database UTIL_DB to role {{SYSADMIN_ROLE}};
grant usage, create stage, create workspace on schema UTIL_DB.PUBLIC to role {{ADMIN_ROLE}};
-- Lesson 8: the SYSADMIN stand-in creates its functions in UTIL_DB.PUBLIC
grant usage, create function on schema UTIL_DB.PUBLIC to role {{SYSADMIN_ROLE}};"""),
    md("## Course data file (the learner's Downloads folder)\nLesson 2 has the learner download `fruits_available_for_smoothies.txt`. "
       "The file is in `data/`; upload it once:\n\n"
       f"```\nsnow sql -q \"use role {ADMIN_ROLE}; put 'file://<path>/data/*' {DOWNLOADS} auto_compress=false overwrite=true\"\n```"),
    sql("create_downloads_stage", f"""use role {{{{ADMIN_ROLE}}}};
create stage if not exists {DOWNLOADS[1:]}
  comment = 'Badge 3: stands in for the learner''s local Downloads folder'
  directory = (enable = true)
  encryption = (type = 'SNOWFLAKE_SSE');
grant read on stage {DOWNLOADS[1:]} to role {{{{SYSADMIN_ROLE}}}};
alter stage {DOWNLOADS[1:]} refresh;
list {DOWNLOADS};"""),
    py("downloads_check", f"""expected = {sorted(DATA_FILES)!r}
found = sorted(n.split('/')[-1] for n in pdf(create_downloads_stage)['name'])
print('Missing course files:', sorted(set(expected) - set(found)) or 'none')"""),
    md("## Teardown (commented out)\nRemoves everything Badge 3 creates."),
    sql("teardown", """-- use role accountadmin;
-- drop database if exists SMOOTHIES;
-- drop function if exists UTIL_DB.PUBLIC.SUM_MYSTERY_BAG_VARS(number, number, number);
-- drop function if exists UTIL_DB.PUBLIC.NEUTRALIZE_WHINING(text);
-- drop resource monitor if exists Four_Daily_Credits;
-- drop stage if exists UTIL_DB.PUBLIC.BADGE3_DOWNLOADS;
-- drop warehouse if exists {{WAREHOUSE}};
-- drop role if exists {{SYSADMIN_ROLE}};
-- drop role if exists {{ADMIN_ROLE}};
select 'teardown is commented out' as status;"""),
]

NB[DORA_SETUP_NB] = [
    md("# Badge 3: DORA setup (course Lesson 2, 🤖 DORA! We Meet Again!)\n\n"
       "⚠️ The cells create the API integration and the GRADER function that call Snowflake Education's external grading service. "
       "They are shared with the other badges; if another badge's DORA setup already ran, these cells recreate the same objects.\n\n"
       "The course page only says to follow the DORA tutorial (create UTIL_DB, the API integration and the GRADER function). "
       "The script below is the same one the other badge courses print (Badge 5 and Badge 4 Lesson 1); it is not in this course's export. "
       "The `DORA_IS_WORKING` test that calls the grader is in `dora/dora_tests.ipynb`."),
    md("### 1. Run the API Integration Script"),
    sql("dora_api_integration", """use role accountadmin;

create or replace api integration dora_api_integration
api_provider = aws_api_gateway
api_aws_role_arn = 'arn:aws:iam::321463406630:role/snowflakeLearnerAssumedRole'
enabled = true
api_allowed_prefixes = ('https://awy6hshxy4.execute-api.us-west-2.amazonaws.com/dev/edu_dora');"""),
    md("### 2. Set up the Grader Function"),
    sql("dora_grader_function", """create or replace external function util_db.public.grader(
      step varchar
    , passed boolean
    , actual integer
    , expected integer
    , description varchar)
returns variant
api_integration = dora_api_integration 
context_headers = (current_timestamp, current_account, current_statement, current_account_name)
as 'https://awy6hshxy4.execute-api.us-west-2.amazonaws.com/dev/edu_dora/grader'
;"""),
]

# ------------------------------------------------------------------ lesson 1
NB["lesson_01_getting_set_up"] = preamble("Lesson 1: Getting Set Up", "Story and lab-environment pages; nothing to run.") + [
    page("👋🏼 Meet Mel"), md("Video and quiz only; nothing to run."),
    page("🔬 Setting Up Your Lab Environment"),
    course("Pre-requisites: Badge 1 (DWW) and Badge 2 (CMCW). Sign up for a Snowflake trial on AWS US West (Oregon), or keep using the trial from the earlier badges."),
    sql("account_details", "select current_organization_name() as org, current_account_name() as account, current_account() as locator,\n"
                           "       current_region() as region, current_user() as user_name;"),
    page("👂 DORA is Listening"),
    course("Create a new DABW link row in the YSA App (https://ysa.snowflakeuniversity.com). Outside Snowflake; nothing to run."),
]

# ------------------------------------------------------------------ lesson 2
NB["lesson_02_getting_started_with_sis"] = preamble(
    "Lesson 2: Getting Started with Streamlit in Snowflake!",
    "The SMOOTHIES database, the Custom Smoothie Order Form app, FRUIT_OPTIONS and the internal stage.") + [
    page("❓ What is Streamlit in Snowflake?"),
    course("Check Your Warehouse: you should have a COMPUTE_WH warehouse owned by SYSADMIN (create it if missing; change ownership if ACCOUNTADMIN owns it)."),
    sql("check_warehouse", "-- Derived solution: owner of the stand-in warehouse\nuse role {{ADMIN_ROLE}};\nshow warehouses like '{{WAREHOUSE}}';"),
    py("check_warehouse_owner", "w = pdf(check_warehouse).iloc[0]\nprint('Warehouse', w['name'], 'owner:', w['owner'], '(course: SYSADMIN; stand-in here:', SYSADMIN_ROLE + ')')"),
    course("Create a Smoothies Database: create a new database named SMOOTHIES, owned by SYSADMIN; the PUBLIC schema also owned by SYSADMIN."),
    sql("create_smoothies", "-- Derived solution (the course gives no code); created as the SYSADMIN stand-in, so it owns the database and PUBLIC\n"
                            "use role {{SYSADMIN_ROLE}};\ncreate database SMOOTHIES;\nuse warehouse {{WAREHOUSE}};\nuse schema SMOOTHIES.PUBLIC;"),
    sql("check_owners", "show databases like 'SMOOTHIES';\n"),
    sql("check_public_owner", "show schemas like 'PUBLIC' in database SMOOTHIES;"),
    course("Configure Your User Preferences: set your default role to SYSADMIN and your default warehouse to COMPUTE_WH; tick the resource-monitor email box. (UI: your name → Settings → Preferences.)"),
    sql("user_defaults", "-- SQL equivalent. Commented out: it changes your own user's defaults account-wide, and here the stand-in role and warehouse are not your real SYSADMIN / COMPUTE_WH.\n"
                         "-- alter user identifier($badge_user) set default_role = {{SYSADMIN_ROLE}} default_warehouse = {{WAREHOUSE}};\nselect 'user defaults left unchanged' as status;"),
    page("👷🏾‍♂️ Let's Make a SiS App"),
    course("Projects → Streamlit → **+ Streamlit App**; App title **Custom Smoothie Order Form**; app location **SMOOTHIES / PUBLIC**; app warehouse **COMPUTE_WH**; Create "
           "(screenshot 2026011315051). DOUBLE-CHECK that you are using SYSADMIN when you create your Streamlit app."),
    sql("create_custom_app", """-- SQL equivalent of the Create Streamlit App dialog
use role {{SYSADMIN_ROLE}};
create streamlit SMOOTHIES.PUBLIC."Custom Smoothie Order Form"
  runtime_name = 'SYSTEM$WAREHOUSE_RUNTIME'
  query_warehouse = {{WAREHOUSE}}
  title = 'Custom Smoothie Order Form';
alter streamlit SMOOTHIES.PUBLIC."Custom Smoothie Order Form" add live version from last;"""),
    course("Let's Make Some Edits: collapse the sidebar, delete everything after line 14 of the sample app, change the title (cup_with_straw emoji) and the write text; Run (screenshots 2026011315052, 053)."),
    app_cell("edit_app_1", "CUSTOM", A1),
    run_app("run_app_1", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    page("➕ Adding Interactivity"),
    course("Paste the Streamlit `st.selectbox` example under your code (screenshots 2026011315071, 072) and Run."),
    app_cell("edit_app_2a", "CUSTOM", A2A),
    course("A Few Tweaks: delete the extra `import streamlit as st`; ask about fruits instead of contact methods (screenshot 2026011315072.png)."),
    app_cell("edit_app_2b", "CUSTOM", A2B),
    run_app("run_app_2b", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    page("🍒 More Fruits to Choose From"),
    course("Create a FRUIT_OPTIONS table in the PUBLIC schema of SMOOTHIES, owned by SYSADMIN: FRUIT_ID a number, FRUIT_NAME text up to 25 characters (screenshot 2026011315100)."),
    sql("create_fruit_options", "-- Derived solution\nuse role {{SYSADMIN_ROLE}};\ncreate table SMOOTHIES.PUBLIC.FRUIT_OPTIONS (\n  FRUIT_ID number,\n  FRUIT_NAME varchar(25)\n);"),
    course("Download the TXT File of Fruit Names & View It: `fruits_available_for_smoothies.txt` (two header rows, `%` delimiter, FRUIT_NAME before FRUIT_ID)."),
    sql("downloaded_file", f"-- The learner's Downloads folder stands in as {DOWNLOADS}\nlist {DOWNLOADS};"),
    course("A FILE FORMAT to Load the Fruit File."),
    sql("create_file_format", code("More Fruits to Choose From")),
    page("📁 Create & Use an Internal Stage"),
    course("Create the Internal Stage and Load the File Into It: Create → Stage → Snowflake Managed; name **my_uploaded_files**; SMOOTHIES.PUBLIC; directory table on; client-side encryption (screenshots 2026011315140, 140-1); "
           "then **+ Files** and upload the TXT file (141, 142)."),
    sql("create_internal_stage", "-- SQL equivalent of the Create Stage dialog (client-side encryption is the default, SNOWFLAKE_FULL)\nuse role {{SYSADMIN_ROLE}};\n"
                                 "create stage SMOOTHIES.PUBLIC.my_uploaded_files\n  directory = (enable = true);"),
    sql("upload_fruit_file", f"-- SQL equivalent of **+ Files** → Upload\ncopy files into @SMOOTHIES.PUBLIC.my_uploaded_files\nfrom {DOWNLOADS}\nfiles = ('fruits_available_for_smoothies.txt');\n"
                             "alter stage SMOOTHIES.PUBLIC.my_uploaded_files refresh;\nlist @SMOOTHIES.PUBLIC.my_uploaded_files;"),
    course("Query the Not-Yet-Loaded Data Using the File Format (template in the course; screenshot 2026011315145 shows the filled-in version)."),
    sql("query_staged_file", "-- From screenshot 2026011315145\nselect $1, $2\nfrom @smoothies.public.my_uploaded_files/fruits_available_for_smoothies.txt\n(file_format => smoothies.public.two_headerrow_pct_delim);"),
    course("Check to See if the File WOULD load (the errors are expected: the file's column order differs from the table's; screenshot 2026011315152)."),
    sql("copy_validation", code("Create & Use an Internal Stage", 1)),
    page("➕ Bring It All Together"),
    course("Reorder Columns During the COPY INTO LOAD (screenshots 2026011315170, 171). PURGE = TRUE removes the file from the stage after loading."),
    sql("copy_into_reordered", "-- From screenshot 2026011315171\nCOPY INTO smoothies.public.fruit_options\nfrom ( select $2 as FRUIT_ID, $1 as FRUIT_NAME\nfrom @smoothies.public.my_uploaded_files/fruits_available_for_smoothies.txt )\n"
                               "file_format = (format_name = smoothies.public.two_headerrow_pct_delim)\non_error = abort_statement\npurge = true;"),
    sql("check_purge", "list @smoothies.public.my_uploaded_files;"),
    course("Display the Fruit Options List in Your SiS App: add the three course lines (screenshot 2026011315174)."),
    app_cell("edit_app_2c", "CUSTOM", A2C),
    run_app("run_app_2c", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    page("🤖 DORA! We Meet Again!"),
    course("Confirm you have a UTIL_DB owned by SYSADMIN with a PUBLIC schema owned by SYSADMIN; follow the DORA link to create the API integration and GRADER function."),
    sql("check_util_db", "-- Derived solution: owner of UTIL_DB and its PUBLIC schema\nshow databases like 'UTIL_DB';"),
    sql("check_util_db_public", "show schemas like 'PUBLIC' in database UTIL_DB;"),
    dora("DORA_IS_WORKING", "the grader responds"),
    page("🤖 DORA DABW001"), dora("DABW001", "FRUIT_OPTIONS has 25 rows"),
]

# ------------------------------------------------------------------ lesson 3
NB["lesson_03_moving_data_from_sis_to_snowflake"] = preamble(
    "Lesson 3: Moving Data from SiS to Snowflake",
    "The col function, the multiselect, the ORDERS table and the order insert.") + [
    page("❄️ The Snowpark COL Function"),
    course("Remove the SelectBox (screenshots 2026011415022, 023), import `col`, and bring back only the FRUIT_NAME column (025, 031)."),
    md("Python, added to the app (not SQL):\n\n```python\n" + code("The Snowpark COL Function") + "\n```"),
    app_cell("edit_app_3a", "CUSTOM", A3A),
    run_app("run_app_3a", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    page("🧰 The Streamlit Multi-select Widget"),
    course("Add a Multiselect and comment out the line that shows the dataframe (screenshot 2026011415051)."),
    app_cell("edit_app_3b", "CUSTOM", A3B),
    course("Display the LIST with `st.write()` and `st.text()` (screenshot 2026011415053)."),
    app_cell("edit_app_3b2", "CUSTOM", A3B2),
    run_app("run_app_3b2", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    page("🧾 Clean Up the GUI & Create an Orders Table"),
    course("Clean Up Empty Brackets with an IF block (screenshots 2026011415063, 071)."),
    app_cell("edit_app_3c", "CUSTOM", A3C),
    course("Create a Place to Store Order Data: a table in SMOOTHIES named ORDERS, owned by SYSADMIN, one text column INGREDIENTS with a 200-character limit (screenshot 2026011415074)."),
    sql("create_orders", "-- From screenshot 2026011415074\nuse role {{SYSADMIN_ROLE}};\ncreate table SMOOTHIES.PUBLIC.ORDERS\n(\ningredients varchar(200)\n);"),
    page("🔀 Converting a LIST to a STRING"),
    course("Create the INGREDIENTS_STRING variable inside the IF block (screenshot 2026011415094); add the FOR block (103); output the string (104)."),
    app_cell("edit_app_3d", "CUSTOM", A3D),
    app_cell("edit_app_3e", "CUSTOM", A3E),
    app_cell("edit_app_3f", "CUSTOM", A3F),
    run_app("run_app_3f", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    page("💾 Storing the Orders in Snowflake"),
    course("Build a SQL Insert Statement & Test It: delete the two write lines, add a space after each fruit name (screenshot 2026011415121) and add the course's `my_insert_stmt` (122)."),
    app_cell("edit_app_3g", "CUSTOM", A3G),
    course("Copy the SQL statement and paste it in a worksheet to make sure it works (screenshots 2026011415122, 124)."),
    sql("test_insert_statement", "-- From screenshot 2026011415124: the statement the app printed\ninsert into smoothies.public.orders(ingredients)\nvalues ('Cantaloupe Guava Jackfruit Elderberries Figs ');"),
    sql("select_orders", "select * from smoothies.public.orders;"),
    course("Insert the Order into Snowflake (screenshot dabw086)."),
    app_cell("edit_app_3h", "CUSTOM", A3H),
    page("🚰 Fixing the Flow"),
    course("Truncate the Orders Table (screenshot dabw089)."),
    sql("truncate_orders", "truncate table smoothies.public.orders;"),
    course("Add a Submit Button (screenshot dabw090)."),
    app_cell("edit_app_3i", "CUSTOM", A3I),
    run_app("run_app_3i", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    course("Submit a Few More Orders: at least 5 DIFFERENT order rows in your table. Each insert below is what one click of Submit Order runs (the statement the app builds)."),
    sql("submit_order_1", "insert into smoothies.public.orders(ingredients) values ('Cantaloupe Ziziphus Jujube Tangerine ');"),
    sql("submit_order_2", "insert into smoothies.public.orders(ingredients) values ('Apples Guava Raspberries Yerba Mate Vanilla Fruit ');"),
    sql("submit_order_3", "insert into smoothies.public.orders(ingredients) values ('Elderberries Ximenia Ziziphus Jujube Tangerine ');"),
    sql("submit_order_4", "insert into smoothies.public.orders(ingredients) values ('Dragon Fruit Honeydew Guava Apples Kiwi ');"),
    sql("submit_order_5", "insert into smoothies.public.orders(ingredients) values ('Cantaloupe Guava Jackfruit Elderberries Figs ');"),
    sql("check_orders", "select * from smoothies.public.orders;"),
    page("🤖 DORA DABW002"), dora("DABW002", "at least 5 different orders"),
]

# ------------------------------------------------------------------ lesson 4
NB["lesson_04_sis_behind_the_scenes"] = preamble(
    "Lesson 4: SiS Behind the Scenes", "The resource monitor and the DABW003 check.") + [
    page("💰 Managing Credit Usage for Your SiS App"),
    course("Navigate to ADMIN → Cost Management → Resource Monitors and set one up that limits credit usage to 4 credits per day for your Account "
           "(screenshot 2026011415202: name **Four_Daily_Credits**, credit quota 4, monitor type Account, resets daily, immediately; "
           "notify at 75%, suspend and notify at 85%, suspend immediately and notify at 95%)."),
    note("A monitor at the **account** level would cap every warehouse on this shared account, so it is attached to the stand-in warehouse instead."),
    sql("create_resource_monitor", """-- SQL equivalent of the New Resource Monitor dialog (screenshot 2026011415202), as the real ACCOUNTADMIN.
-- The dialog's Monitor Type is Account; here the monitor is assigned to the stand-in warehouse instead.
use role accountadmin;
create resource monitor Four_Daily_Credits with
  credit_quota = 4
  frequency = daily
  start_timestamp = immediately
  triggers on 75 percent do notify
           on 85 percent do suspend
           on 95 percent do suspend_immediate;
alter warehouse {{WAREHOUSE}} set resource_monitor = Four_Daily_Credits;
-- restore context
use role {{SYSADMIN_ROLE}};
use warehouse {{WAREHOUSE}};"""),
    sql("check_resource_monitor", "use role accountadmin;\nshow resource monitors like 'Four_Daily_Credits';\nuse role {{SYSADMIN_ROLE}};\nuse warehouse {{WAREHOUSE}};"),
    page("🐍 Importing Python Libraries"), md("Reading only."),
    page("⚠️ Exceeded My Quota? Wut?"), md("Reading only (the page describes raising the monitor's daily credits when the quota message appears)."),
    page("🤖 DORA DABW003"), dora("DABW003", "a mystery check: ASCII of the fruit name starting with Z"),
]

# ------------------------------------------------------------------ lesson 5
NB["lesson_05_prototype_reviews_and_sprint_planning"] = preamble(
    "Lesson 5: Prototype Reviews & Sprint Planning", "NAME_ON_ORDER, the Pending Smoothie Orders app and ORDER_FILLED.") + [
    page("🧬 Mel Presents His Prototype"), md("Reading only."),
    page("🏃🏽‍♂️‍➡️ Planning Sprint #2"), md("Reading only."),
    page("📥 Adding a Text Input Box"),
    course("Move Your Import COL Function Statement to Top of Code (screenshots 2026011415295, 300)."),
    app_cell("edit_app_5a", "CUSTOM", A5A),
    course("Add a Name Box for Smoothie Orders (screenshots 2026011415300.png, 301, 301-1)."),
    app_cell("edit_app_5b", "CUSTOM", A5B),
    run_app("run_app_5b", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    page("➕ Adding a Column to the Orders Table"),
    course("Use the ALTER Command to Add a New Column to Your Orders Table: NAME_ON_ORDER (screenshots 2026011415314, 314-1)."),
    sql("add_name_on_order", "-- From screenshot 2026011415314-1\nalter table SMOOTHIES.PUBLIC.ORDERS add column name_on_order varchar(100);"),
    page("➕ Writing the Name to the Table"),
    course("Update the insert statement to include the name and print it with `st.write` and `st.stop()` (screenshots 2026011415324, 325)."),
    app_cell("edit_app_5c", "CUSTOM", A5C),
    course("Uh-oh. Our statement isn't actually valid (screenshot 2026011415325-1, 330). The statement the app printed, run as the course shows it:"),
    sql("invalid_insert", protected("insert into smoothies.public.orders(ingredients) values ('Dragon Fruit Honeydew Guava Apples Kiwi ','MellyMel');")),
    course("Fix the Insert Statement & Finish the Task: the column list needs `name_on_order` too (screenshot 2026011415330)."),
    sql("fixed_insert", "-- From screenshot 2026011415330\ninsert into smoothies.public.orders(ingredients, name_on_order) values ('Elderberries Ximenia Ziziphus Jujube Tangerine ','MellyMel');\n"),
    sql("select_named_orders", "select * from smoothies.public.orders\nwhere name_on_order is not null;"),
    course("Update your code so the app does the INSERT, and (the fun extra step) add the NAME_ON_ORDER value to the success message (screenshot 2026011415331)."),
    app_cell("edit_app_5d", "CUSTOM", A5D),
    run_app("run_app_5d", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    sql("submit_named_orders", "-- Orders submitted through the app (the statement it builds)\ninsert into smoothies.public.orders(ingredients, name_on_order) values ('Cantaloupe Dragon Fruit Blueberries ','Kristl');\n"
                               "insert into smoothies.public.orders(ingredients, name_on_order) values ('Jackfruit Kiwi Orange Elderberries Yerba Mate ','Gynger');\n"
                               "insert into smoothies.public.orders(ingredients, name_on_order) values ('Kiwi Elderberries Figs Ximenia ','Kai');"),
    page("✅ To-Do #2: A 2nd SiS App for the Kitchen"),
    course("Build a New SiS App: **Pending Smoothie Orders**, in the SMOOTHIES database and PUBLIC schema. Either create it from scratch or duplicate the existing app and edit it (screenshot 2026011415455)."),
    sql("create_pending_app", """-- SQL equivalent of Duplicate (⋮ → Duplicate): a new app in SMOOTHIES.PUBLIC
use role {{SYSADMIN_ROLE}};
create streamlit SMOOTHIES.PUBLIC."Pending Smoothie Orders"
  runtime_name = 'SYSTEM$WAREHOUSE_RUNTIME'
  query_warehouse = {{WAREHOUSE}}
  title = 'Pending Smoothie Orders';
alter streamlit SMOOTHIES.PUBLIC."Pending Smoothie Orders" add live version from last;"""),
    py("duplicate_app_code", "# a duplicate starts with the original app's code\nwrite_app(PENDING, r'''" + A5D + "''')"),
    course("Add a column named ORDER_FILLED to the ORDERS table: BOOLEAN, `DEFAULT FALSE` right after the word BOOLEAN."),
    sql("add_order_filled", "-- Derived solution (the course gives the column name, type and default)\nalter table SMOOTHIES.PUBLIC.ORDERS add column ORDER_FILLED boolean default false;"),
    course("Mark some rows as filled before testing the app (the course's code)."),
    sql("mark_old_orders_filled", code("To-Do #2", 0)),
    course("Delete everything after the `session` and `my_dataframe =` lines and filter to unfilled orders with the course's FILTER code; stop when your app looks like screenshot 2026011415465."),
    app_cell("edit_pending_1", "PENDING", P1),
    page("🖼️ An Editable Dataframe"),
    course("Convert Your Dataframe to a Data Editor (screenshot 2026011415480): `editable_df = st.data_editor(my_dataframe)`. The first version above already includes that line."),
    run_app("run_pending_1", 'SMOOTHIES.PUBLIC."Pending Smoothie Orders"'),
    page("♻️ Capturing Changes to Data"),
    course("Add a Submit Button (screenshot 2026011415494)."),
    app_cell("edit_pending_2", "PENDING", P2),
    run_app("run_pending_2", 'SMOOTHIES.PUBLIC."Pending Smoothie Orders"'),
    page("🤖 DORA DABW004"), dora("DABW004", "ORDER_FILLED is BOOLEAN with default FALSE"),
]

# ------------------------------------------------------------------ lesson 6
NB["lesson_06_pending_orders_app_improvements"] = preamble(
    "Lesson 6: Pending Orders App Improvements", "The order sequence, ownership audit, the final ORDERS definition and the merge.") + [
    page("❄️ Ensuring Uniqueness"),
    course("Create a Sequence to Use as a Row ID (screenshots 2026011612105, 111-1): ORDER_SEQ in SMOOTHIES.PUBLIC, created as SYSADMIN."),
    sql("create_order_seq", "-- From screenshot 2026011612111-1\nuse role {{SYSADMIN_ROLE}};\ncreate sequence smoothies.public.order_seq\n    start = 1\n    increment = 2\n    ORDER\n    comment = 'Provide a unique id for each smoothie order';"),
    course("Truncate the Orders Table, then add the unique ID column (screenshot 2026011612111)."),
    sql("truncate_orders", "truncate table SMOOTHIES.PUBLIC.ORDERS;"),
    sql("add_order_uid", code("Ensuring Uniqueness")),
    page("🔐 Checking All Objects for SYSADMIN Ownership"),
    course("Audit Ownership of All Your Objects: make sure they are all owned by the SYSADMIN role (video)."),
    sql("ownership_audit", "-- Derived solution (the course shows a video): owners of the objects created so far\n"
                           "select 'DATABASE' as kind, database_name as name, database_owner as owner from smoothies.information_schema.databases where database_name = 'SMOOTHIES'\n"
                           "union all select 'SCHEMA', schema_name, schema_owner from smoothies.information_schema.schemata where schema_name = 'PUBLIC'\n"
                           "union all select 'TABLE', table_name, table_owner from smoothies.information_schema.tables where table_schema = 'PUBLIC'\n"
                           "union all select 'STAGE', stage_name, stage_owner from smoothies.information_schema.stages\n"
                           "union all select 'FILE FORMAT', file_format_name, file_format_owner from smoothies.information_schema.file_formats where file_format_schema = 'PUBLIC'\n"
                           "union all select 'SEQUENCE', sequence_name, sequence_owner from smoothies.information_schema.sequences;"),
    sql("streamlit_owners", "show streamlit apps in schema SMOOTHIES.PUBLIC;"),
    course("Test Your Apps: submit a few orders in the ordering app and make sure they arrive in the Pending Orders app."),
    sql("submit_test_orders", "insert into smoothies.public.orders(ingredients, name_on_order) values ('Dragon Fruit Honeydew Guava Tangerine ','Betty Jean');\n"
                              "select * from smoothies.public.orders;"),
    page("🧾 Perfecting the ORDERS Table Definition"),
    course("Drop and recreate the table with the course's definition (this also gives a fresh start on orders)."),
    sql("recreate_orders", code("Perfecting the ORDERS Table Definition")),
    sql("check_orders_owner", "show tables like 'ORDERS' in schema SMOOTHIES.PUBLIC;"),
    course("Test Your SiS Apps Again (screenshots 2026011612213, 213-1): submit an order, then mark it filled."),
    sql("submit_again", "insert into smoothies.public.orders(ingredients, name_on_order) values ('Dragon Fruit Honeydew Guava Tangerine ','Betty Jean');"),
    course("Add a Merge Statement (course code, inside `if submitted:`; screenshot 2026011612224 shows the lines). `when_matched` is imported with `col`."),
    app_cell("edit_pending_3", "PENDING", P3),
    note("The course's merge statement is run by clicking Submit in the app; the SQL equivalent of ticking ORDER_FILLED for an order and clicking Submit follows."),
    sql("tick_filled", "-- SQL equivalent of ticking ORDER_FILLED and clicking Submit (the merge matches rows by ORDER_UID)\nmerge into smoothies.public.orders o\n"
                       "using (select order_uid, true as order_filled from smoothies.public.orders where name_on_order = 'Betty Jean') e\non o.order_uid = e.order_uid\nwhen matched then update set order_filled = e.order_filled;\n"),
    page("🧾 Improving the Pending Orders App"),
    course("Making the Success Message More Meaningful (try/except around the merge) and Making the GUI Look Better (no table or Submit button when there are no pending orders); screenshots 2026011612224, 230, 231."),
    app_cell("edit_pending_4", "PENDING", P4),
    run_app("run_pending_4", 'SMOOTHIES.PUBLIC."Pending Smoothie Orders"'),
    page("🍒 To-Do #3: A Way to Limit Fruits Added"),
    course("Limit entries with `max_selections=5` on the multiselect (screenshots 2026011612245, 250)."),
    app_cell("edit_app_6", "CUSTOM", A6),
    run_app("run_app_6", 'SMOOTHIES.PUBLIC."Custom Smoothie Order Form"'),
    page("🟢 Smoothie Fridays Are A GO"), md("Story only."),
    page("🤖 DORA DABW005"), dora("DABW005", "two SiS apps (EXECUTE STREAMLIT queries) exist in query history"),
]

# ------------------------------------------------------------------ lesson 7
NB["lesson_07_intro_to_interfaces"] = preamble("Lesson 7: Intro to Interfaces", "Reading, quizzes and browsing public websites; nothing to run in Snowflake.") + [
    page("🎛️ Interfaces: More Than Just Faces!"), md("Reading and quiz only."),
    page("🌐 Melanie's Favorite Website"), course("Try the USDA FoodData Central search and URL hacking (https://fdc.nal.usda.gov/). Outside Snowflake; nothing to run."),
    page("📞 Data Sourcing Options from FoodData Central"), md("Reading and quiz only."),
    page("🤖 Using an API"), course("Explore the SmoothieFroot website (https://smoothiefroot.com): run the sample API calls and edit the URLs. Outside Snowflake; nothing to run."),
    page("🥳 Smoothie Fridays are a Hit"), md("Story only."),
]

# ------------------------------------------------------------------ lesson 8
NB["lesson_08_variables_and_udfs"] = preamble(
    "Lesson 8: Intro to Variables and Variable-Driven Loading", "Local variables, the SUM_MYSTERY_BAG_VARS UDF and NEUTRALIZE_WHINING.") + [
    page("💬 Zena Checks In on Mel"), md("Story only."),
    page("❓ A Mystery Bag Called a Variable"),
    course("Create & Set a Local SQL Variable (screenshot 2026011615014); Run a Select that Displays the Variable (015); Change the Value and Run the Select Again (015.jpg); Do More With More Variables (020)."),
    sql("set_mystery_bag", "set mystery_bag = 'What is in here?';"),
    sql("select_mystery_bag", "select $mystery_bag;"),
    sql("change_mystery_bag", "set mystery_bag = 'This bag is empty!!';\n\nselect $mystery_bag;"),
    sql("more_variables", "set var1 = 2;\nset var2 = 5;\nset var3 = 7;\n\nselect $var1+$var2+$var3;"),
    page("📁 A Code Organizer Called a Function"),
    course("Create a Simple User Defined Function (UDF). Put your function in your UTIL_DB database! (screenshot 2026011615075.png)."),
    sql("create_sum_function", "-- From screenshot 2026011615075.png, created in UTIL_DB.PUBLIC as the SYSADMIN stand-in\nuse role {{SYSADMIN_ROLE}};\nuse schema UTIL_DB.PUBLIC;\n"
                               "create function sum_mystery_bag_vars (var1 number, var2 number, var3 number)\n returns number as 'select var1+var2+var3';"),
    course("Run Your New Function (screenshot 2026011615075.jpg)."),
    sql("run_sum_function", "select sum_mystery_bag_vars (12,36,204);"),
    course("Combine Local Variables & Function Calls (screenshot 2026011615084.jpg)."),
    sql("combine_variables", "set eeny = 4;\nset meeny = 67.2;\nset miney_mo = -39;\n\nselect sum_mystery_bag_vars ($eeny,$meeny,$miney_mo);"),
    page("🤖 DORA DABW006"),
    course("This, That & The Other: set the three local variables to -10.5, 2 and 1000, in the same session as the check."),
    sql("dabw006_variables", "-- The values the course asks for. The DORA check (dora/dora_tests) sets them again in its own session.\nset this = -10.5;\nset that = 2;\nset the_other = 1000;"),
    sql("dabw006_function_check", "select util_db.public.sum_mystery_bag_vars($this,$that,$the_other);"),
    dora("DABW006", "the function sums the three local variables to 991.5"),
    page("⛙ Combining UDFs with Snowflake Functions"),
    course("Using a System Function to Fix a Variable Value (screenshot 2026011615201.jpg): set a phrase with alternating caps and use INITCAP()."),
    sql("alternating_caps", "set alternating_caps_phrase = 'aLtErNaTiNg CaPs!';\n\nselect $alternating_caps_phrase;"),
    sql("initcap_example", "set alternating_caps_phrase = 'wHy ArE yOu lIkE tHiS?';\n\nselect initcap($alternating_caps_phrase);"),
    course("🎯 CHALLENGE LAB: Write a UDF that Neutralizes Alternating Caps Phrases: in UTIL_DB.PUBLIC, named NEUTRALIZE_WHINING, one TEXT argument, returns TEXT, first letter of each word capitalized and the rest lower case (use INITCAP)."),
    sql("create_neutralize_whining", "-- Derived solution (the course gives the requirements, not the code)\nuse role {{SYSADMIN_ROLE}};\nuse schema UTIL_DB.PUBLIC;\n"
                                     "create function neutralize_whining(phrase text)\n returns text as 'select initcap(phrase)';"),
    sql("test_neutralize_whining", "select neutralize_whining('bUt mOm i wAsHeD tHe dIsHes yEsTeRdAy');"),
    page("🤖 DORA DABW007"), dora("DABW007", "NEUTRALIZE_WHINING works"),
]

# ------------------------------------------------------------------ lesson 9-10
NB["lesson_09_getting_ready_for_snis"] = preamble("Lesson 9: Getting Ready for SniS", "GitHub and the Streamlit repo; all outside Snowflake.") + [
    page("♻️ Change is Inevitable"), md("Quiz only."),
    page("💾 About GitHub Accounts"), course("Create a GitHub account if you don't have one (github.com). Outside Snowflake; nothing to run."),
    page("🪣 Set Up a GitHub Repo"), course("Create a new repo in your GitHub account. Outside Snowflake; nothing to run."),
    page("🐍 Copy the SiS Code into a New Py File"),
    course("Download the Python file (and environment.yaml) from your SiS app; create streamlit_app.py and requirements.txt in your repo. Outside Snowflake; nothing to run."),
    page("🛠️ Modify the Repo Files"),
    course("Make the SiS → SniS changes to streamlit_app.py and requirements.txt (connection code from the course screenshots). Outside Snowflake; nothing to run."),
]
NB["lesson_10_streamlit_the_og"] = preamble("Lesson 10: Streamlit (The OG!)", "A Streamlit account, GitHub access and the connection secrets; all outside Snowflake.") + [
    page("🛠️ Set Up a Streamlit Account and Give It Access to Your GitHub Account"), course("Sign up at https://streamlit.io and link GitHub. Outside Snowflake; nothing to run."),
    page("⚙️ Create an App in the New Streamlit Account"), course("Create the app from your repo. Outside Snowflake; nothing to run."),
    page("🛜 Fill in Connection Details"), course("Add the connection parameters to the app's secrets (Streamlit documentation). Outside Snowflake; nothing to run."),
    page("🪪 Add the Account ID"),
    course("Copy your Account Identifier (change the dot to a dash) into the secrets."),
    sql("account_identifier", "-- What the Snowsight account menu shows: organization-account\nselect current_organization_name() || '-' || current_account_name() as account_identifier;"),
    page("🧪 Test to Make Sure the App is Working"), course("Test both apps. Outside Snowflake; nothing to run."),
]

# ------------------------------------------------------------------ lesson 11
NB["lesson_11_using_api_data_with_variables"] = preamble(
    "Lesson 11: Using API Data With Variables", "SEARCH_ON and the final DORA records. The SniS (Streamlit not in Snowflake) code changes run outside Snowflake.") + [
    page("🧪 Take the Keys"), md("Quiz only."),
    page("📩 Bringing Data into the App via API"),
    course("Add the `requests` library to requirements.txt and streamlit_app.py of your SniS project and call the SmoothieFroot API (screenshots 2026011615430-440). Outside Snowflake; nothing to run."),
    page("📊 Using SmoothieFroot Data More Effectively"), course("Rearrange the SniS app's code to show nutrition data for the fruits chosen. Outside Snowflake; nothing to run."),
    page("👨‍🍳 Using the Ingredients Chosen in the API Call"), course("Use the fruit_chosen variable in the API call. Outside Snowflake; nothing to run."),
    page("📋 Requirements Negotiation"), md("Reading only."),
    page("✅ Updating the Multi-Select Part 1"),
    course("🎯 Let's Add the SEARCH_ON Field to Our FRUIT-OPTIONS Table: add the column SEARCH_ON; copy FRUIT_NAME into it with an UPDATE; then fix the rows that need a different value "
           "(at least Apples, Blueberries, Jack Fruit, Raspberries and Strawberries; Ximenia is in SmoothieFroot, just written differently). Screenshots 2026011616025."),
    sql("add_search_on", "-- Derived solution (screenshot 2026011616025.jpg shows the shape)\nuse role {{SYSADMIN_ROLE}};\nalter table smoothies.public.fruit_options add column SEARCH_ON varchar(25);"),
    sql("seed_search_on", "--copy name to seed the columns - then we can just edit the problem rows\nupdate smoothies.public.fruit_options\nset search_on = fruit_name;"),
    sql("fix_search_on", "-- The values below are the names https://my.smoothiefroot.com/api/fruit/all returns (checked 2026-11-19)\n"
                         "update smoothies.public.fruit_options set search_on = 'Apple' where fruit_name = 'Apples';\n"
                         "update smoothies.public.fruit_options set search_on = 'Blueberry' where fruit_name = 'Blueberries';\n"
                         "update smoothies.public.fruit_options set search_on = 'Raspberry' where fruit_name = 'Raspberries';\n"
                         "update smoothies.public.fruit_options set search_on = 'Strawberry' where fruit_name = 'Strawberries';\n"
                         "update smoothies.public.fruit_options set search_on = 'Ximenia (Hog Plum)' where fruit_name = 'Ximenia';"),
    sql("check_search_on", "select * from smoothies.public.fruit_options order by fruit_id;"),
    page("✅ Updating the Multi-Select Part 2"),
    course("Add the SEARCH_ON column to the dataframe that feeds the multiselect, bring in pandas as pd, make `pd_df`, and use the loc/iloc statement (screenshots 2026011616040-050). Outside Snowflake (SniS); nothing to run."),
    page("✨ Putting on the Finishing Touches"),
    course("Preparing Records for Your Final DORA Check: create three orders using your app, with the fruits in the order described. Kevin: Apples, Lime, Ximenia (NOT filled). "
           "Divya: Dragon Fruit, Guava, Figs, Jackfruit, Blueberries (FILLED). Xi: Vanilla Fruit, Nectarine (FILLED). If you mess this up you can truncate the table and start over."),
    sql("truncate_orders", "-- the course allows a truncate to start over\ntruncate table smoothies.public.orders;"),
    sql("order_kevin", "-- the statement the ordering app builds on Submit Order (each fruit followed by a space)\ninsert into smoothies.public.orders(ingredients, name_on_order) values ('Apples Lime Ximenia ','Kevin');"),
    sql("order_divya", "insert into smoothies.public.orders(ingredients, name_on_order) values ('Dragon Fruit Guava Figs Jackfruit Blueberries ','Divya');"),
    sql("order_xi", "insert into smoothies.public.orders(ingredients, name_on_order) values ('Vanilla Fruit Nectarine ','Xi');"),
    sql("mark_filled", "-- SQL equivalent of ticking ORDER_FILLED for Divya and Xi in the Pending Smoothie Orders app and clicking Submit\n"
                       "update smoothies.public.orders set order_filled = true where name_on_order in ('Divya','Xi');"),
    sql("final_orders", "select * from smoothies.public.orders order by order_uid;"),
    page("🤖 DORA DABW008"), dora("DABW008", "the Kevin, Divya and Xi orders"),
    page("🎉 Badge Time!"), course("Check in with DORA in the YSA app: DABW001 to DABW008 should be PASSING and VALID. Outside Snowflake; nothing to run."),
]

# ------------------------------------------------------------------ DORA tests
DORA_STEPS = [("DORA_IS_WORKING", "DORA! We Meet Again", 2, 0), ("DABW001", "DORA DABW001", 2, 0), ("DABW002", "DORA DABW002", 3, 0),
              ("DABW003", "DORA DABW003", 4, 0), ("DABW004", "DORA DABW004", 5, 0), ("DABW005", "DORA DABW005", 6, 0),
              ("DABW006", "DORA DABW006", 8, 0), ("DABW007", "DORA DABW007", 8, 0), ("DABW008", "DORA DABW008", 11, 0)]
LESSON_FILE = {2: "lesson_02_getting_started_with_sis", 3: "lesson_03_moving_data_from_sis_to_snowflake", 4: "lesson_04_sis_behind_the_scenes",
               5: "lesson_05_prototype_reviews_and_sprint_planning", 6: "lesson_06_pending_orders_app_improvements",
               8: "lesson_08_variables_and_udfs", 11: "lesson_11_using_api_data_with_variables"}
dora_cells = [
    md("# Badge 3: DORA checks\n\nEvery DORA step from the course, in order. Each check has two cells:\n\n"
       "1. **Local check**: the course's check query with the external `GRADER` call removed. It runs entirely in this account and sends nothing.\n"
       "2. **DORA (exact course code)**: verbatim and unedited (DORA audits a hash of the code).\n\n"
       "⚠️ **Running a DORA cell sends data outside this account** to Snowflake Education's grading service. Run only the local checks unless you intend to submit.\n\n"
       "Each check is meant to be run at the end of its lesson: later lessons rewrite the objects earlier checks read (for example ORDERS). "
       "DABW005 reads `SNOWFLAKE.ACCOUNT_USAGE`, which can lag by up to a few hours."),
    md("## Set your worksheet drop lists"),
    py("dora_vars", f'WAREHOUSE = "{WAREHOUSE}"   # stands in for the course\'s COMPUTE_WH'),
    sql("dora_context", "use role accountadmin;\nuse warehouse {{WAREHOUSE}};\nuse database util_db;\nuse schema public;"),
]
for step, key, lesson, idx in DORA_STEPS:
    c = code(key, idx)
    if step == "DABW006":
        c_exact = c.replace("set this = ;", "set this = -10.5;").replace("set that = ;", "set that = 2;").replace("set the_other =  ;", "set the_other = 1000;")
        assert c_exact != c
        c = c_exact
        local = dora_local(c)
    else:
        local = dora_local(c)
    assert "grader(" not in re.sub(r"--.*", "", local).lower(), step
    where = f"after `{LESSON_FILE[lesson]}`"
    dora_cells += [md(f"## {step} ({where})")]
    if step == "DABW006":
        dora_cells.append(md("The course's code has blanks for the three local variables (`set this = ;`). They are filled in with the values the page asks for (-10.5, 2, 1000); "
                             "nothing else is changed."))
    dora_cells.append(sql(f"{step.lower()}_local", "-- Local check: same query without the GRADER call\n" + local))
    if step == "DABW005":
        dora_cells.append(sql("dabw005_strict", "-- Not a course cell: the same test, but the pattern is built so this query's own text cannot match it\n"
                              "select count(*) as app_queries\nfrom (\n  select query_text from snowflake.account_usage.query_history\n  where query_text like 'execute streamlit' || '%'\n  group by query_text)\n;"))
    dora_cells.append(sql(f"{step.lower()}_dora", c))
NB[DORA_NB] = dora_cells

META = {"jupytext": {"main_language": "sql"}, "kernelspec": {"display_name": "Streamlit Notebook", "name": "streamlit"}}
for sub in ("data", "dora", "tools"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
for sub in ("", "dora"):
    for old in [f for f in os.listdir(os.path.join(OUT, sub)) if f.endswith(".ipynb")]:
        os.remove(os.path.join(OUT, sub, old))
for name, src in DATA_FILES.items():
    shutil.copy(os.path.join(COURSE, "assets", src), os.path.join(OUT, "data", name))
for name, cells in NB.items():
    names = [c["metadata"].get("name") for c in cells if c["cell_type"] == "code"]
    assert len(names) == len(set(names)), (name, [n for n in names if names.count(n) > 1])
    json.dump({"cells": cells, "metadata": META, "nbformat": 4, "nbformat_minor": 5}, open(os.path.join(OUT, f"{name}.ipynb"), "w"), indent=1)
    print(f"{name:52s} cells={len(cells):3d}  code={len(names):3d}")
shutil.copy(os.path.abspath(__file__), os.path.join(OUT, "tools", os.path.basename(__file__)))
