"""Fix class-name allergy matching and add common medicines the checks can resolve.

Revision ID: 0005
Revises: 0004

1. find_allergy_conflicts() in the baseline compared `NOT (ing.substance_id = al.substance_id)`. For an allergy that names
   a drug CLASS ("sulfa", "NSAIDs", "macrolides") substance_id is NULL, so the comparison is NULL and every family match
   was silently dropped. Only allergies naming one drug (penicillin) ever produced a family conflict. Found by the
   synthetic Margaret set. The fix uses IS DISTINCT FROM.

2. The starter list only knew allergy-relevant drugs, so ordinary medicines (metformin, amlodipine...) were "unresolved".
   That is the safe behaviour, but it meant nearly every plan with an allergy showed "could not check" on every line and
   the omission catch (which stays silent while any new line is unresolved) could never fire. These are plain names for
   RESOLUTION only: no family membership, no clinical meaning. The list is still unreviewed; the app keeps its banner.
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# (normalized name, display name, synonyms)
COMMON = [
    # heart and blood pressure
    ("amlodipine", "Amlodipine", []), ("atenolol", "Atenolol", []), ("metoprolol", "Metoprolol", []), ("bisoprolol", "Bisoprolol", []),
    ("carvedilol", "Carvedilol", []), ("propranolol", "Propranolol", []), ("losartan", "Losartan", []), ("telmisartan", "Telmisartan", []),
    ("valsartan", "Valsartan", []), ("olmesartan", "Olmesartan", []), ("ramipril", "Ramipril", []), ("enalapril", "Enalapril", []),
    ("lisinopril", "Lisinopril", []), ("hydrochlorothiazide", "Hydrochlorothiazide", ["hctz"]), ("chlorthalidone", "Chlorthalidone", []),
    ("furosemide", "Furosemide", ["frusemide"]), ("torsemide", "Torsemide", []), ("spironolactone", "Spironolactone", []),
    ("nifedipine", "Nifedipine", []), ("diltiazem", "Diltiazem", []), ("verapamil", "Verapamil", []),
    ("atorvastatin", "Atorvastatin", []), ("rosuvastatin", "Rosuvastatin", []), ("simvastatin", "Simvastatin", []),
    ("clopidogrel", "Clopidogrel", []), ("warfarin", "Warfarin", []), ("apixaban", "Apixaban", []), ("rivaroxaban", "Rivaroxaban", []),
    ("digoxin", "Digoxin", []), ("isosorbide mononitrate", "Isosorbide mononitrate", []), ("nitroglycerin", "Nitroglycerin", ["glyceryl trinitrate"]),
    # diabetes
    ("metformin", "Metformin", []), ("glimepiride", "Glimepiride", []), ("gliclazide", "Gliclazide", []), ("glipizide", "Glipizide", []),
    ("sitagliptin", "Sitagliptin", []), ("vildagliptin", "Vildagliptin", []), ("linagliptin", "Linagliptin", []), ("teneligliptin", "Teneligliptin", []),
    ("dapagliflozin", "Dapagliflozin", []), ("empagliflozin", "Empagliflozin", []), ("pioglitazone", "Pioglitazone", []), ("insulin", "Insulin", []),
    # stomach
    ("pantoprazole", "Pantoprazole", []), ("omeprazole", "Omeprazole", []), ("esomeprazole", "Esomeprazole", []), ("rabeprazole", "Rabeprazole", []),
    ("famotidine", "Famotidine", []), ("domperidone", "Domperidone", []), ("ondansetron", "Ondansetron", []), ("loperamide", "Loperamide", []),
    ("lactulose", "Lactulose", []),
    # pain and fever
    ("paracetamol", "Paracetamol", ["acetaminophen"]), ("tramadol", "Tramadol", []),
    # breathing and allergy
    ("salbutamol", "Salbutamol", ["albuterol"]), ("levosalbutamol", "Levosalbutamol", []), ("montelukast", "Montelukast", []),
    ("cetirizine", "Cetirizine", []), ("levocetirizine", "Levocetirizine", []), ("fexofenadine", "Fexofenadine", []),
    ("budesonide", "Budesonide", []), ("formoterol", "Formoterol", []), ("tiotropium", "Tiotropium", []),
    # hormones and bones
    ("levothyroxine", "Levothyroxine", ["thyroxine"]), ("carbimazole", "Carbimazole", []), ("prednisolone", "Prednisolone", []),
    ("dexamethasone", "Dexamethasone", []), ("methylprednisolone", "Methylprednisolone", []), ("alendronate", "Alendronate", []),
    # brain and mood
    ("levetiracetam", "Levetiracetam", []), ("phenytoin", "Phenytoin", []), ("carbamazepine", "Carbamazepine", []),
    ("sodium valproate", "Sodium valproate", ["valproate"]), ("gabapentin", "Gabapentin", []), ("pregabalin", "Pregabalin", []),
    ("sertraline", "Sertraline", []), ("escitalopram", "Escitalopram", []), ("amitriptyline", "Amitriptyline", []),
    ("clonazepam", "Clonazepam", []), ("alprazolam", "Alprazolam", []), ("donepezil", "Donepezil", []), ("levodopa", "Levodopa", []), ("carbidopa", "Carbidopa", []),
    # other common
    ("allopurinol", "Allopurinol", []), ("febuxostat", "Febuxostat", []), ("colchicine", "Colchicine", []),
    ("calcium carbonate", "Calcium carbonate", ["calcium"]), ("cholecalciferol", "Cholecalciferol", ["vitamin d3", "vitamin d"]),
    ("folic acid", "Folic acid", []), ("ferrous sulfate", "Ferrous sulfate", ["iron"]), ("cyanocobalamin", "Cyanocobalamin", ["vitamin b12"]),
    ("hydroxychloroquine", "Hydroxychloroquine", []), ("tamsulosin", "Tamsulosin", []), ("finasteride", "Finasteride", []), ("oxybutynin", "Oxybutynin", []),
    # anti-infectives (no allergy family membership is added here)
    ("metronidazole", "Metronidazole", []), ("ciprofloxacin", "Ciprofloxacin", []), ("levofloxacin", "Levofloxacin", []),
    ("doxycycline", "Doxycycline", []), ("nitrofurantoin", "Nitrofurantoin", []), ("fluconazole", "Fluconazole", []),
    ("acyclovir", "Acyclovir", ["aciclovir"]), ("oseltamivir", "Oseltamivir", []), ("albendazole", "Albendazole", []), ("trimethoprim", "Trimethoprim", []),
]


def _esc(v: str) -> str:
    return v.replace("'", "''")


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION find_allergy_conflicts(p_item_id uuid)
    RETURNS TABLE (allergy_id uuid, match match_type, ingredient_id uuid, family_id uuid)
    LANGUAGE sql STABLE AS $$
      WITH item AS (SELECT patient_id FROM care_plan_items WHERE id = p_item_id),
      al AS (
        SELECT a.* FROM allergies a JOIN item i ON a.patient_id = i.patient_id
        WHERE a.is_current AND a.active
      ),
      ing AS (SELECT mi.id, mi.substance_id FROM medicine_ingredients mi WHERE mi.item_id = p_item_id)
      SELECT al.id, 'direct'::match_type, ing.id, NULL::uuid
        FROM al JOIN ing ON ing.substance_id IS NOT NULL AND ing.substance_id = al.substance_id
      UNION ALL
      SELECT al.id, 'drug_family'::match_type, ing.id, fm.family_id
        FROM al
        JOIN ing ON ing.substance_id IS NOT NULL
        JOIN drug_family_members fm ON fm.substance_id = ing.substance_id
       WHERE (fm.family_id = al.family_id
              OR fm.family_id IN (SELECT m2.family_id FROM drug_family_members m2 WHERE m2.substance_id = al.substance_id))
         AND ing.substance_id IS DISTINCT FROM al.substance_id      -- a class allergy has no substance_id (NULL)
      UNION ALL
      SELECT NULL::uuid, 'unresolved'::match_type, ing.id, NULL::uuid
        FROM ing
       WHERE ing.substance_id IS NULL AND EXISTS (SELECT 1 FROM al)
    $$;
    """)
    values = ",\n".join(
        "  ('%s', '%s', ARRAY[%s]::text[], ARRAY[]::text[])" % (_esc(n), _esc(d), ", ".join("'%s'" % _esc(x) for x in syn))
        for n, d, syn in COMMON)
    op.execute("""
    INSERT INTO drug_substances (substance_normalized, display_name, synonyms, brand_names) VALUES
    %s
    ON CONFLICT (substance_normalized) DO NOTHING;
    """ % values)


def downgrade() -> None:
    op.execute("DELETE FROM drug_substances WHERE substance_normalized IN (%s) AND id NOT IN (SELECT substance_id FROM drug_family_members)"
               % ", ".join("'%s'" % _esc(n) for n, _d, _s in COMMON))
    # The corrected function is kept on downgrade: restoring the bug would not be a rollback anyone wants.
