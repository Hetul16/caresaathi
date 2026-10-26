-- STARTER DATA ONLY. NOT CLINICALLY REVIEWED. review_status stays 'unreviewed' until a doctor or
-- pharmacist signs it off. The app must show a "reference list not reviewed" banner and must never run
-- allergy checks for real patients while any family used by the check is unreviewed.
-- Cross-reactivity between classes (for example penicillins and cephalosporins) is NOT modelled here;
-- that decision belongs to the reviewer, not to this seed.

BEGIN;

INSERT INTO drug_families (code, name, synonyms, notes) VALUES
  ('penicillins',    'Penicillins',                 ARRAY['penicillin', 'penicillins', 'beta-lactam penicillin'], 'Starter list'),
  ('cephalosporins', 'Cephalosporins',              ARRAY['cephalosporin', 'cephalosporins'],                     'Starter list'),
  ('sulfonamides',   'Sulfonamide antibiotics',     ARRAY['sulfa', 'sulfonamide', 'sulpha'],                      'Starter list'),
  ('nsaids',         'NSAIDs',                      ARRAY['nsaid', 'nsaids', 'anti-inflammatory'],                'Starter list'),
  ('macrolides',     'Macrolides',                  ARRAY['macrolide', 'macrolides'],                             'Starter list');

INSERT INTO drug_substances (substance_normalized, display_name, synonyms, brand_names) VALUES
  ('penicillin',            'Penicillin',            ARRAY['penicillin v', 'penicillin g', 'benzylpenicillin'], ARRAY[]::text[]),
  ('amoxicillin',           'Amoxicillin',           ARRAY['amoxycillin'],                                      ARRAY['Mox', 'Novamox']),
  ('ampicillin',            'Ampicillin',            ARRAY[]::text[],                                           ARRAY[]::text[]),
  ('cloxacillin',           'Cloxacillin',           ARRAY[]::text[],                                           ARRAY[]::text[]),
  ('flucloxacillin',        'Flucloxacillin',        ARRAY[]::text[],                                           ARRAY[]::text[]),
  ('piperacillin',          'Piperacillin',          ARRAY[]::text[],                                           ARRAY[]::text[]),
  ('clavulanic acid',       'Clavulanic acid',       ARRAY['clavulanate'],                                      ARRAY[]::text[]),
  ('cefixime',              'Cefixime',              ARRAY[]::text[],                                           ARRAY[]::text[]),
  ('cefuroxime',            'Cefuroxime',            ARRAY[]::text[],                                           ARRAY[]::text[]),
  ('ceftriaxone',           'Ceftriaxone',           ARRAY[]::text[],                                           ARRAY[]::text[]),
  ('cephalexin',            'Cephalexin',            ARRAY['cefalexin'],                                        ARRAY[]::text[]),
  ('sulfamethoxazole',      'Sulfamethoxazole',      ARRAY['sulphamethoxazole'],                                ARRAY[]::text[]),
  ('ibuprofen',             'Ibuprofen',             ARRAY[]::text[],                                           ARRAY['Brufen']),
  ('diclofenac',            'Diclofenac',            ARRAY[]::text[],                                           ARRAY['Voveran']),
  ('naproxen',              'Naproxen',              ARRAY[]::text[],                                           ARRAY[]::text[]),
  ('aspirin',               'Aspirin',               ARRAY['acetylsalicylic acid'],                             ARRAY['Disprin']),
  ('azithromycin',          'Azithromycin',          ARRAY[]::text[],                                           ARRAY['Azee']),
  ('clarithromycin',        'Clarithromycin',        ARRAY[]::text[],                                           ARRAY[]::text[]);

INSERT INTO drug_family_members (family_id, substance_id)
SELECT f.id, s.id FROM (VALUES
  ('penicillins',    'penicillin'),
  ('penicillins',    'amoxicillin'),
  ('penicillins',    'ampicillin'),
  ('penicillins',    'cloxacillin'),
  ('penicillins',    'flucloxacillin'),
  ('penicillins',    'piperacillin'),
  ('cephalosporins', 'cefixime'),
  ('cephalosporins', 'cefuroxime'),
  ('cephalosporins', 'ceftriaxone'),
  ('cephalosporins', 'cephalexin'),
  ('sulfonamides',   'sulfamethoxazole'),
  ('nsaids',         'ibuprofen'),
  ('nsaids',         'diclofenac'),
  ('nsaids',         'naproxen'),
  ('nsaids',         'aspirin'),
  ('macrolides',     'azithromycin'),
  ('macrolides',     'clarithromycin')
) AS v(fam, sub)
JOIN drug_families f ON f.code = v.fam
JOIN drug_substances s ON s.substance_normalized = v.sub;

COMMIT;
