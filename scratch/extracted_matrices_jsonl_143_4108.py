Created At: 2026-05-28T14:17:46Z
Completed At: 2026-05-28T14:17:46Z
File Path: `file:///c:/Users/pc/source/sgeplus/app/routes/matrices.py`
Total Lines: 312
Total Bytes: 13806
Showing lines 155 to 265
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
155:                          current_matrix_id=matrix_id)
156: 
157: @matrices_bp.route('/descriptors/import', methods=['POST'])
158: def import_descriptors():
159:     from app.models import ImportJob
160:     if ImportJob.is_any_running():
161:         flash('Não é possível realizar importações enquanto houver outra em andamento. Por favor, aguarde a conclusão.', 'warning')
162:         return redirect(url_for('matrices.list_descriptors'))
163: 
164:     form = ImportDescriptorForm()
165:     
166:     if form.validate_on_submit():
167:         file = form.file.data
168:         filename = secure_filename(file.filename)
169:         
170:         try:
171:             if filename.endswith('.csv'):
172:                 df = pd.read_csv(file, sep=';', encoding='utf-8', dtype=str)
173:             else:
174:                 df = pd.read_excel(file, dtype=str)
175:             
176:             # Validate columns
177:             required_cols = ['Matriz de Referência', 'Tema', 'Ano Escolar', 'Disciplina', 'Código', 'Descrição']
178:             missing_cols = [col for col in required_cols if col not in df.columns]
179:             if missing_cols:
180:                 flash(f'Arquivo inválido. Colunas ausentes: {", ".join(missing_cols)}', 'danger')
181:                 return redirect(url_for('matrices.list_descriptors'))
182:             
183:             # Pre-load lookups (Name -> ID)
184:             matrices = {m.name: m.id for m in ReferenceMatrix.query.all()}
185:             themes = {(t.name, t.matrix_id): t.id for t in Theme.quer
<truncated 2015 bytes>
a {row_num}: Disciplina '{subject_name}' não encontrada.")
225:                     continue
226:                 
227:                 descriptor = Descriptor(
228:                     code=code,
229:                     description=desc_text,
230:                     matrix_id=matrix_id,
231:                     theme_id=theme_id,
232:                     school_year_id=year_id,
233:                     subject_id=subject_id
234:                 )
235:                 new_descriptors.append(descriptor)
236:             
237:             if errors:
238:                 # If any errors, abort and show all errors (up to 5 for brevity in flash)
239:                 for err in errors[:5]:
240:                     flash(err, 'danger')
241:                 if len(errors) > 5:
242:                     flash(f'E mais {len(errors) - 5} erros...', 'danger')
243:                 return redirect(url_for('matrices.list_descriptors'))
244:             
245:             # Bulk save
246:             for d in new_descriptors:
247:                 db.session.add(d)
248:             
249:             db.session.commit()
250:             flash(f'{len(new_descriptors)} descritores importados com sucesso!', 'success')
251:             
252:         except Exception as e:
253:             db.session.rollback()
254:             flash(f'Erro ao processar arquivo: {str(e)}', 'danger')
255:             
256:     else:
257:         for field, errors in form.errors.items():
258:             for error in errors:
259:                 flash(f'Erro no campo {field}: {error}', 'danger')
260: 
261:     return redirect(url_for('matrices.list_descriptors'))
262: 
263: @matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])
264: def edit_descriptor(id):
265:     descriptor = Descriptor.query.get_or_404(id)
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
