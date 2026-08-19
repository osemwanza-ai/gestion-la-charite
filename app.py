from flask import Flask, render_template, request, redirect, url_for, send_file
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
    montant = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=True)

class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    matricule = db.Column(db.String(50), unique=True, nullable=False)
    telephone_tuteur = db.Column(db.String(20), nullable=True)
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

# --- ROUTES DE L'APPLICATION ---

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
        montant = float(request.form.get('montant', 0))
        description = request.form.get('description', '')

        nouveau_frais = ConfigurationFrais(
            type_frais=type_frais,
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
            return "Erreur : Le frais d'inscription n'a pas encore été paramétré dans l'administration.", 400

        nom = request.form.get('nom_complet')
        classe = request.form.get('classe')
        telephone = request.form.get('telephone_tuteur')
        date_actuelle = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        count = Eleve.query.count() + 1
        matricule = f"CHAR-{datetime.now().year}-{count:03d}"

        nouvel_eleve = Eleve(
            nom_complet=nom,
            classe=classe,
            matricule=matricule,
            telephone_tuteur=telephone,
            date_inscription=date_actuelle
        )
        db.session.add(nouvel_eleve)
        db.session.flush()

        paiement_ins = Paiement(
            date_heure=date_actuelle,
            eleve_id=nouvel_eleve.id,
            nom_eleve=nom,
            classe=classe,
            categorie_frais='INSCRIPTION',
            montant=frais_inscription.montant,
            motif_detail="Frais d'inscription obligatoire"
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
            return "Erreur : Vous devez sélectionner un élève inscrit.", 400
            
        eleve = Eleve.query.get(eleve_id)
        if not eleve:
            return "Erreur : Élève non trouvé dans la base.", 400

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
    liste = Eleve.query.order_by(Eleve.nom_complet.asc()).all()
    return render_template('eleves.html', eleves=liste)

@app.route('/download/<type_rapport>')
def download_rapport(type_rapport):
    wb = openpyxl.Workbook()
    ws = wb.active

    if type_rapport == 'inscription':
        ws.title = "Frais d'Inscription"
        ws.append(["N°", "Date & Heure", "Matricule", "Élève", "Classe", "Montant Payé"])
        paiements = Paiement.query.filter_by(categorie_frais='INSCRIPTION').all()
        for p in paiements:
            e = Eleve.query.get(p.eleve_id)
            ws.append([p.id, p.date_heure, e.matricule if e else '-', p.nom_eleve, p.classe, p.montant])

    elif type_rapport == 'minerval':
        ws.title = "Frais de Minerval"
        ws.append(["N°", "Date & Heure", "Élève", "Classe", "Trimestre", "Montant Payé"])
        paiements = Paiement.query.filter_by(categorie_frais='MINERVAL').all()
        for p in paiements:
            ws.append([p.id, p.date_heure, p.nom_eleve, p.classe, p.trimestre, p.montant])

    elif type_rapport == 'technique':
        ws.title = "Frais Techniques et Connexes"
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
