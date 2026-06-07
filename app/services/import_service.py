import pandas as pd
import re
from datetime import datetime

class ImportService:
    @staticmethod
    def process_file(file_storage, type='student', task_id=None):
        """
        Reads an Excel file and returns a list of dictionaries with cleaned data.
        type: 'student', 'professor', 'modulation' or 'class'
        """
        try:
            df = pd.read_excel(file_storage)
        except Exception as e:
            return {"success": False, "error": f"Erro ao ler arquivo: {str(e)}"}
            
        # Define Columns based on type
        required_cols = {
            'student': ["Unidade de Ensino", "Nome da Turma", "Nome Completo", "Sexo", "Data de Nascimento", "CPF", "Cor/Raça", "Nacionalidade", "País nascimento", "Deficiência"],
            'professor': ["Nome Completo", "Data de Nascimento", "Sexo", "Cor/Raça", "CPF"],
            'class': ["Nome da Turma", "Ano Escolar", "Unidade de Ensino", "Turno", "Estrutura Curricular"],
            'modulation': ["INEP da Escola", "Unidade de Ensino", "Nome da Turma", "CPF", "Componente"],
            'quilombola': ["Nome"],
            'indigenous': ["Nome"]
        }
        
        required = required_cols.get(type)
        if not required:
             return {"success": False, "error": "Tipo de importação inválido."}
            
        # Check columns
        missing = [col for col in required if col not in df.columns]
        if missing:
            return {"success": False, "error": f"Colunas faltando: {', '.join(missing)}"}
            
        results = []
        errors = []
        
        # Load Cache for Validation (to avoid N+1 queries)
        from app.models import TeachingUnit, Class, Subject, SchoolYear, CurriculumStructure, City
        from app.import_utils import start_import_task, update_import_progress
        
        # Total count for reference
        total = len(df)
        
        if task_id:
            start_import_task(total, task_id=task_id)

        schools_cache = {}
        schools_inep_cache = {}
        cities_cache = {}
        classes_cache = {} # Key: (SchoolID, ClassName) -> ClassID
        subjects_cache = {}
        years_cache = {}
        structures_cache = {}
        
        # Pre-load caches
        all_schools = TeachingUnit.query.filter_by(type='Escola').all()
        for s in all_schools:
            schools_cache[s.name.strip().lower()] = s.id
            if s.inep_code:
                schools_inep_cache[s.inep_code.strip()] = s.id
            
        if type in ['student', 'professor']:
            all_cities = City.query.all()
            for c in all_cities:
                if c.uf:
                    cities_cache[f"{c.uf.lower()}_{c.name.strip().lower()}"] = c.id
            
        all_classes = Class.query.all()
        for c in all_classes:
            if c.teaching_unit_id:
                 key = (c.teaching_unit_id, c.name.strip().lower())
                 classes_cache[key] = c.id
                 
        if type == 'modulation':
            all_subjects = Subject.query.all()
            for s in all_subjects:
                subjects_cache[s.name.strip().lower()] = s.id
        
        if type == 'class':
            all_years = SchoolYear.query.all()
            for y in all_years:
                years_cache[y.name.strip().lower()] = y.id
            all_structures = CurriculumStructure.query.all()
            for s in all_structures:
                structures_cache[s.name.strip().lower()] = s.id

        for index, row in df.iterrows():
            row_num = index + 2 
            item_data = {}
            
            if task_id and index % 10 == 0:
                update_import_progress(task_id, index, message=f"Lendo e validando registro {index} de {total}...")
            
            if type in ['quilombola', 'indigenous']:
                name = str(row.get("Nome", "")).strip()
                if not name or name.lower() == 'nan':
                    errors.append(f"Linha {row_num}: Nome é obrigatório.")
                    continue
                item_data = {'name': name}
                
            elif type == 'class':
                class_name = str(row.get("Nome da Turma", "")).strip()
                year_name = str(row.get("Ano Escolar", "")).strip()
                unit_name = str(row.get("Unidade de Ensino", "")).strip()
                shift = str(row.get("Turno", "")).strip()
                structure_name = str(row.get("Estrutura Curricular", "")).strip()
                
                if not class_name or not year_name or not unit_name or not shift or not structure_name:
                    errors.append(f"Linha {row_num}: Todos os campos são obrigatórios.")
                    continue
                
                year_id = years_cache.get(year_name.lower())
                unit_id = schools_cache.get(unit_name.lower())
                struct_id = structures_cache.get(structure_name.lower())
                
                if not year_id: errors.append(f"Linha {row_num}: Ano '{year_name}' não encontrado."); continue
                if not unit_id: errors.append(f"Linha {row_num}: Unidade '{unit_name}' não encontrada."); continue
                if not struct_id: errors.append(f"Linha {row_num}: Estrutura '{structure_name}' não encontrada."); continue
                
                valid_shifts = ['Matutino', 'Vespertino', 'Noturno', 'Integral']
                if shift not in valid_shifts:
                    errors.append(f"Linha {row_num}: Turno '{shift}' inválido."); continue
                
                item_data = {
                    'name': class_name,
                    'year_id': year_id,
                    'unit_id': unit_id,
                    'shift': shift,
                    'structure_id': struct_id
                }

            elif type == 'modulation':
                school_inep = str(row.get("INEP da Escola", row.get("INEP", ""))).strip()
                school_name = str(row.get("Unidade de Ensino", "")).strip()
                class_name = str(row.get("Nome da Turma", "")).strip()
                cpf_raw = str(row.get("CPF", "")).strip()
                subject_name = str(row.get("Componente", row.get("Disciplina", ""))).strip()
                
                if (not school_inep or school_inep == 'nan') and (not school_name or school_name == 'nan'):
                    errors.append(f"Linha {row_num}: Unidade de Ensino ou INEP é obrigatório.")
                    continue

                if not class_name or class_name == 'nan' or not cpf_raw or cpf_raw == 'nan' or not subject_name or subject_name == 'nan':
                    errors.append(f"Linha {row_num}: Turma, CPF e Componente são obrigatórios.")
                    continue
                     
                cpf_clean = re.sub(r'[^0-9]', '', cpf_raw)
                if len(cpf_clean) != 11:
                    errors.append(f"Linha {row_num}: CPF inválido ({cpf_raw}).")
                    continue
                 
                unit_id = None
                if school_inep and school_inep != 'nan':
                    if school_inep.endswith('.0'):
                        school_inep = school_inep[:-2]
                    unit_id = schools_inep_cache.get(school_inep)
                    
                if not unit_id:
                    unit_id = schools_cache.get(school_name.lower())

                if not unit_id:
                    errors.append(f"Linha {row_num}: Unidade de Ensino não encontrada (INEP: '{school_inep}', Nome: '{school_name}').")
                    continue
                     
                class_id = classes_cache.get((unit_id, class_name.lower()))
                if not class_id:
                    errors.append(f"Linha {row_num}: Turma não encontrada na unidade informada ({class_name} - {school_name}).")
                    continue
                     
                sub_id = subjects_cache.get(subject_name.lower())
                if not sub_id:
                    errors.append(f"Linha {row_num}: Componente não encontrado ({subject_name}).")
                    continue
                     
                item_data = {
                     'cpf': cpf_clean,
                     'class_id': class_id,
                     'subject_id': sub_id,
                     'school_id': unit_id
                }
            
            else:
                # Student or Professor
                name = str(row.get("Nome Completo", "")).strip()
                cpf_raw = str(row.get("CPF", "")).strip()
                dob_raw = row.get("Data de Nascimento")
                race_raw = str(row.get("Cor/Raça", "")).strip()
                
                if not name or name == 'nan' or not cpf_raw or cpf_raw == 'nan' or not dob_raw or pd.isna(dob_raw) or not race_raw or race_raw == 'nan' or not str(row.get("Sexo", "")).strip():
                     errors.append(f"Linha {row_num}: Todos os campos básicos são obrigatórios (Nome, Nascimento, Sexo, Raça, CPF).")
                     continue
                
                sex_raw = str(row.get("Sexo", "")).strip().lower()
                sex_val = "Nao Informado"
                if sex_raw in ['m', 'masculino']: sex_val = "Masculino"
                elif sex_raw in ['f', 'feminino']: sex_val = "Feminino"
                
                cpf_clean = re.sub(r'[^0-9]', '', cpf_raw)
                if len(cpf_clean) != 11:
                    errors.append(f"Linha {row_num}: CPF inválido ({cpf_raw}).")
                    continue
                # item_data will use cpf_clean below
                
                dob_obj = None
                if isinstance(dob_raw, datetime):
                    dob_obj = dob_raw.date()
                else:
                    try:
                        dob_str = str(dob_raw)
                        for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                            try:
                                dob_obj = datetime.strptime(dob_str, fmt).date()
                                break
                            except: pass
                    except: pass
                
                if not dob_obj:
                    errors.append(f"Linha {row_num}: Data de Nascimento inválida ({dob_raw}).")
                    continue
                    
                race_map = {'branca': 'Branca', 'preta': 'Preta', 'parda': 'Parda', 'amarela': 'Amarela', 'indigena': 'Indigena', 'indígena': 'Indigena', 'nao informado': 'Nao Informado', 'não informado': 'Nao Informado'}
                race_val = race_map.get(race_raw.lower(), 'Nao Informado')
                
                # Novos campos em comum e saneamento
                inep_raw = str(row.get("Código INEP", "")).strip()
                sus_raw = str(row.get("Cartão SUS", "")).strip()
                
                nationality = str(row.get("Nacionalidade", "Brasileiro")).strip()
                if nationality.lower() == 'nan' or not nationality: nationality = 'Brasileiro'
                
                birth_country = str(row.get("País nascimento", "Brasil")).strip()
                if birth_country.lower() == 'nan' or not birth_country: birth_country = 'Brasil'
                
                birth_state_raw = str(row.get("UF Naturalidade", "")).strip()[:2].upper()
                birth_city_raw = str(row.get("Município Naturalidade", "")).strip()
                birth_city_id = None
                
                if birth_city_raw and birth_city_raw != 'nan':
                    if birth_state_raw and birth_state_raw != 'NAN':
                        birth_city_id = cities_cache.get(f"{birth_state_raw.lower()}_{birth_city_raw.lower()}")
                    else:
                        for key, cid in cities_cache.items():
                            if key.endswith(f"_{birth_city_raw.lower()}"):
                                birth_city_id = cid
                                birth_state_raw = key.split('_')[0].upper()
                                break
                    
                res_zone_raw = str(row.get("Zona Residencial", "")).strip()
                res_zone = "Urbana" if res_zone_raw.lower() in ['urbana', 'u'] else "Rural" if res_zone_raw.lower() in ['rural', 'r'] else None
                
                diff_loc_raw = str(row.get("Localização Diferenciada de Residência", "")).strip()
                
                item_data = {
                    'name': name,
                    'cpf': cpf_clean,
                    'cpf_clean': cpf_clean,
                    'birth_date': dob_obj,
                    'sex': sex_val,
                    'race': race_val,
                    'inep_code': inep_raw if inep_raw and inep_raw != 'nan' else None,
                    'sus_card': sus_raw if sus_raw and sus_raw != 'nan' else None,
                    'nationality': nationality,
                    'birth_country': birth_country,
                    'birth_state': birth_state_raw if birth_state_raw and birth_state_raw != 'NAN' else None,
                    'birth_city_id': birth_city_id,
                    'residential_zone': res_zone,
                    'differentiated_location': diff_loc_raw if diff_loc_raw and diff_loc_raw != 'nan' else None
                }
                
                email_raw = str(row.get("E-mail", "")).strip()
                if email_raw and email_raw.lower() != 'nan':
                    item_data['email'] = email_raw
                    
                if type == 'student':
                    family_income_raw = str(row.get("Renda Familiar", "")).strip()
                    if family_income_raw and family_income_raw.lower() != 'nan':
                        item_data['family_income'] = family_income_raw
                        
                    school_name = str(row.get("Unidade de Ensino", "")).strip()
                    class_name = str(row.get("Nome da Turma", "")).strip()
                    school_inep = str(row.get("INEP da Escola", row.get("INEP", ""))).strip()
                    
                    unit_id = None
                    if school_inep and school_inep != 'nan':
                        if school_inep.endswith('.0'):
                            school_inep = school_inep[:-2]
                        unit_id = schools_inep_cache.get(school_inep)
                        
                    if not unit_id:
                        if not school_name or school_name == 'nan':
                            errors.append(f"Linha {row_num}: Unidade e Turma são obrigatórios para alunos.")
                            continue
                        unit_id = schools_cache.get(school_name.lower())
                        
                    if not class_name or class_name == 'nan':
                         errors.append(f"Linha {row_num}: Unidade e Turma são obrigatórios para alunos.")
                         continue
                    
                    if not unit_id:
                        errors.append(f"Linha {row_num}: Unidade de Ensino não encontrada (INEP: '{school_inep}', Nome: '{school_name}').")
                        continue
                        
                    class_id = classes_cache.get((unit_id, class_name.lower()))
                    if not class_id:
                        errors.append(f"Linha {row_num}: Turma não encontrada na unidade ({class_name} - {school_name}).")
                        continue
                        
                    # New student-specific fields
                    deficiency_raw = str(row.get("Deficiência", "Não")).strip().lower()
                    has_disability = True if deficiency_raw in ['sim', 's', 'true', '1'] else False

                    bolsa_raw = str(row.get("Bolsa Família", "Não") if "Bolsa Família" in row else row.get("O aluno é beneficiário do Bolsa Família?", "Não")).strip().lower()
                    has_bolsa = True if bolsa_raw in ['sim', 's', 'true', '1'] else False

                    dietary_raw = str(row.get("Restrições Alimentares", "")).strip()
                    dietary_list = []
                    if dietary_raw and dietary_raw.lower() != 'nan':
                        dietary_list = [d.strip() for d in dietary_raw.split(',') if d.strip()]
                        
                    is_quilombola_raw = str(row.get("É Quilombola?", "Não")).strip().lower()
                    is_quilombola = True if is_quilombola_raw in ['sim', 's', 'true', '1'] else False
                    
                    quilombola_community_raw = str(row.get("Comunidade Quilombola", "")).strip()
                    indigenous_people_raw = str(row.get("Povo Indígena", "")).strip()

                    item_data.update({
                        'teaching_unit_id': unit_id,
                        'class_id': class_id,
                        'special_needs': has_disability,
                        'bolsa_familia': has_bolsa,
                        'dietary_restrictions': dietary_list,
                        'is_quilombola': is_quilombola,
                        'quilombola_community_name': quilombola_community_raw if is_quilombola and quilombola_community_raw and quilombola_community_raw != 'nan' else None,
                        'indigenous_people_name': indigenous_people_raw if race_val == 'Indigena' and indigenous_people_raw and indigenous_people_raw != 'nan' else None
                    })
                
                elif type == 'professor':
                    email = str(row.get("E-mail", "")).strip()
                    if email and email != 'nan':
                         item_data['email'] = email
            
            results.append(item_data)
            
        return {"success": True, "data": results, "errors": errors}
