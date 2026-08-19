from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
import openpyxl
from io import BytesIO
from datetime import datetime
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'app_database.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODÈLES DE BASE DE DONNÉES ---

class ConfigurationFrais(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type_frais = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(50), nullable=False)
    option = db.Column(db.String(100), nullable=True)
    montant = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=True)

class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(50), unique=True, nullable=False)
    nom_complet = db.Column(db.String(100), nullable=False)
    sexe = db.Column(db.String(10), nullable=True)
    date_naissance = db.Column(db.String(50), nullable=True)
    lieu_naissance = db.Column(db.String(100), nullable=True)
    adresse = db.Column(db.String(200), nullable=True)
    nom_responsables = db.Column(db.String(100), nullable=False)
    lien_parente = db.Column(db.String(50), nullable=True)
    telephone_principal = db.Column(db.String(20), nullable=False)
    telephone_secondaire = db.Column(db.String(20), nullable=True)
    section = db.Column(db.String(50), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    option = db.Column(db.String(100), nullable=True)
    date_inscription = db.Column(db.String(50), nullable=False)

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_heure = db.Column(db.String(50), nullable=False)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleve.id'), nullable=False)
    nom_eleve = db.Column(db.String(100), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    categorie_frais = db.Column(db.String(50), nullable=False)
    trimestre = db.Column(db.String(20), nullable=True)
    motif_detail = db.Column(db.String(150), nullable=True)
    montant = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

# --- ROUTES ---

@app.route('/')
def dashboard():
    total_eleves = Eleve.query.count()
    paiements = Paiement.query.all()
    total_recettes = sum(p.montant for p in paiements)
    return render_template('dashboard.html', total_eleves=total_eleves, total_recettes=total_recettes)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        type_frais = request.form.get('type_frais')
        section = request.form.get('section')
        option = request.form.get('option', '')
        montant = float(request.form.get('montant', 0))
        description = request.form.get('description', '')

        nouveau_frais = ConfigurationFrais(
            type_frais=type_frais,
            section=section,
            option=option if section in ['Secondaire', 'Humanités'] else 'N/A',
            montant=montant,
            description=description
        )
        db.session.add(nouveau_frais)
        db.session.commit()
        return redirect(url_for('admin'))

    frais_configures = ConfigurationFrais.query.all()
    return render_template('admin.html', frais=frais_configures)

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    frais_inscription = ConfigurationFrais.query.filter_by(type_frais='INSCRIPTION').first()

    if request.method == 'POST':
        if not frais_inscription:
            return "Erreur : Le frais d'inscription doit être configuré dans l'Espace Admin.", 400

        nom = request.form.get('nom_complet')
        sexe = request.form.get('sexe')
        date_naiss = request.form.get('date_naissance')
        lieu_naiss = request.form.get('lieu_naissance')
        adresse = request.form.get('adresse')

        responsable = request.form.get('nom_responsables')
        lien = request.form.get('lien_parente')
        tel1 = request.form.get('telephone_principal')
        tel2 = request.form.get('telephone_secondaire')

        section = request.form.get('section')
        classe = request.form.get('classe')
        option = request.form.get('option', 'N/A')

        date_actuelle = datetime.now().strftime("%d/%m/%Y %H:%M")
        count = Eleve.query.count() + 1
        matricule = f"CHAR-{datetime.now().year}-{count:03d}"

        nouvel_eleve = Eleve(
            matricule=matricule,
            nom_complet=nom,
            sexe=sexe,
            date_naissance=date_naiss,
            lieu_naissance=lieu_naiss,
            adresse=adresse,
            nom_responsables=responsable,
            lien_parente=lien,
            telephone_principal=tel1,
            telephone_secondaire=tel2,
            section=section,
            classe=classe,
            option=option if section in ['Secondaire', 'Humanités'] else 'N/A',
            date_inscription=date_actuelle
        )
        db.session.add(nouvel_eleve)
        db.session.flush()

        paiement_ins = Paiement(
            date_heure=date_actuelle,
            eleve_id=nouvel_eleve.id,
            nom_eleve=nom,
            classe=f"{classe} - {section}",
            categorie_frais='INSCRIPTION',
            montant=frais_inscription.montant,
            motif_detail="Frais d'inscription"
        )
        db.session.add(paiement_ins)
        db.session.commit()

        return redirect(url_for('eleves'))

    return render_template('inscription.html', frais=frais_inscription)

@app.route('/paiements', methods=['GET', 'POST'])
def paiements():
    eleves_inscrits = Eleve.query.order_by(Eleve.nom_complet.asc()).all()
    frais_autorises = ConfigurationFrais.query.all()
    donnees_recu = None

    if request.method == 'POST':
        eleve_id = request.form.get('eleve_id')
        if not eleve_id:
            return "Erreur : Veuillez sélectionner un élève inscrit.", 400

        eleve = Eleve.query.get(eleve_id)
        categorie = request.form.get('categorie_frais')
        trimestre = request.form.get('trimestre')
        motif = request.form.get('motif_detail')
        montant = float(request.form.get('montant', 0))
        date_actuelle = datetime.now().strftime("%d/%m/%Y %H:%M")

        nouveau_p = Paiement(
            date_heure=date_actuelle,
            eleve_id=eleve.id,
            nom_eleve=eleve.nom_complet,
            classe=eleve.classe,
            categorie_frais=categorie,
            trimestre=trimestre if categorie == 'MINERVAL' else '-',
            motif_detail=motif,
            montant=montant
        )
        db.session.add(nouveau_p)
        db.session.commit()

        donnees_recu = {
            'nom': eleve.nom_complet,
            'classe': eleve.classe,
            'categorie': categorie,
            'trimestre': trimestre,
            'montant': montant,
            'date_heure': date_actuelle
        }

    return render_template('paiements.html', eleves=eleves_inscrits, frais_liste=frais_autorises, recu=donnees_recu)

@app.route('/eleves')
def eleves():
    query = Eleve.query

    f_section = request.args.get('section')
    f_classe = request.args.get('classe')
    f_frais = request.args.get('type_frais')

    if f_section:
        query = query.filter_by(section=f_section)
    if f_classe:
        query = query.filter(Eleve.classe.ilike(f"%{f_classe}%"))
    
    eleves_liste = query.order_by(Eleve.nom_complet.asc()).all()

    # Filtrage selon le paiement effectif si le filtre de frais est activé
    if f_frais:
        eleves_filtrer = []
        for e in eleves_liste:
            paiements_e = Paiement.query.filter_by(eleve_id=e.id).all()
            if f_frais == 'INSCRIPTION' and any(p.categorie_frais == 'INSCRIPTION' for p in paiements_e):
                eleves_filtrer.append(e)
            elif f_frais == 'MINERVAL_T1' and any(p.categorie_frais == 'MINERVAL' and p.trimestre == '1er Trimestre' for p in paiements_e):
                eleves_filtrer.append(e)
            elif f_frais == 'MINERVAL_T2' and any(p.categorie_frais == 'MINERVAL' and p.trimestre == '2ème Trimestre' for p in paiements_e):
                eleves_filtrer.append(e)
            elif f_frais == 'MINERVAL_T3' and any(p.categorie_frais == 'MINERVAL' and p.trimestre == '3ème Trimestre' for p in paiements_e):
                eleves_filtrer.append(e)
            elif f_frais == 'TECHNIQUE' and any(p.categorie_frais == 'TECHNIQUE' for p in paiements_e):
                eleves_filtrer.append(e)
            elif f_frais == 'CONNEXE' and any(p.categorie_frais == 'CONNEXE' for p in paiements_e):
                eleves_filtrer.append(e)
        eleves_liste = eleves_filtrer

    return render_template('eleves.html', eleves=eleves_liste)

@app.route('/api/eleve/<int:eleve_id>')
def api_eleve_details(eleve_id):
    eleve = Eleve.query.get_or_404(eleve_id)
    paiements = Paiement.query.filter_by(eleve_id=eleve.id).all()
    configs = ConfigurationFrais.query.all()

    # Calculs Financiers par Categorie
    bilan = []
    
    # Categories à analyser
    categories_frais = [
        ('INSCRIPTION', 'Inscription', '-'),
        ('MINERVAL', 'Minerval - 1er Trimestre', '1er Trimestre'),
        ('MINERVAL', 'Minerval - 2ème Trimestre', '2ème Trimestre'),
        ('MINERVAL', 'Minerval - 3ème Trimestre', '3ème Trimestre'),
        ('TECHNIQUE', 'Frais Technique', '-'),
        ('CONNEXE', 'Frais Connexe', '-')
    ]

    for cat_code, libelle, trim in categories_frais:
        # Trouver la config tarifaire applicable (par section)
        config_tarif = ConfigurationFrais.query.filter_by(type_frais=cat_code, section=eleve.section).first()
        if not config_tarif:
            config_tarif = ConfigurationFrais.query.filter_by(type_frais=cat_code).first()

        exige = config_tarif.montant if config_tarif else 0.0

        if trim != '-':
            paye = sum(p.montant for p in paiements if p.categorie_frais == cat_code and p.trimestre == trim)
        else:
            paye = sum(p.montant for p in paiements if p.categorie_frais == cat_code)

        reste = exige - paye if exige > 0 else 0.0

        bilan.append({
            'libelle': libelle,
            'exige': exige,
            'paye': paye,
            'reste': max(0.0, reste)
        })

    return jsonify({
        'matricule': eleve.matricule,
        'nom_complet': eleve.nom_complet,
        'sexe': eleve.sexe,
        'date_naissance': eleve.date_naissance or 'N/A',
        'lieu_naissance': eleve.lieu_naissance or 'N/A',
        'adresse': eleve.adresse or 'N/A',
        'nom_responsables': eleve.nom_responsables,
        'lien_parente': eleve.lien_parente,
        'telephone_principal': eleve.telephone_principal,
        'telephone_secondaire': eleve.telephone_secondaire or 'N/A',
        'section': eleve.section,
        'classe': eleve.classe,
        'option': eleve.option or 'N/A',
        'date_inscription': eleve.date_inscription,
        'bilan': bilan
    })

@app.route('/download/<type_rapport>')
def download_rapport(type_rapport):
    wb = openpyxl.Workbook()
    ws = wb.active

    if type_rapport == 'inscription':
        ws.title = "Inscriptions"
        ws.append(["N°", "Date & Heure", "Matricule", "Élève", "Section / Classe", "Tuteur", "Téléphone", "Montant Payé"])
        paiements = Paiement.query.filter_by(categorie_frais='INSCRIPTION').all()
        for p in paiements:
            e = Eleve.query.get(p.eleve_id)
            ws.append([
                p.id, p.date_heure, e.matricule if e else '-', p.nom_eleve, p.classe,
                e.nom_responsables if e else '-', e.telephone_principal if e else '-', p.montant
            ])

    elif type_rapport == 'minerval':
        ws.title = "Minerval"
        ws.append(["N°", "Date & Heure", "Élève", "Classe", "Trimestre", "Montant Payé"])
        paiements = Paiement.query.filter_by(categorie_frais='MINERVAL').all()
        for p in paiements:
            ws.append([p.id, p.date_heure, p.nom_eleve, p.classe, p.trimestre, p.montant])

    elif type_rapport == 'technique':
        ws.title = "Frais Techniques & Connexes"
        ws.append(["N°", "Date & Heure", "Élève", "Classe", "Catégorie", "Motif / Option", "Montant Payé"])
        paiements = Paiement.query.filter(Paiement.categorie_frais.in_(['TECHNIQUE', 'CONNEXE'])).all()
        for p in paiements:
            ws.append([p.id, p.date_heure, p.nom_eleve, p.classe, p.categorie_frais, p.motif_detail, p.montant])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"rapport_{type_rapport}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == '__main__':
    app.run()
