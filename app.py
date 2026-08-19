from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import openpyxl
from io import BytesIO
from datetime import datetime
import os

app = Flask(__name__)

# Base de données PostgreSQL
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if not db_url:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_url = f"sqlite:///{os.path.join(BASE_DIR, 'charite.db')}"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modèles de base de données
class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    matricule = db.Column(db.String(50), unique=True, nullable=False)
    telephone_tuteur = db.Column(db.String(20), nullable=True)

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_heure = db.Column(db.String(50), nullable=False)
    nom_eleve = db.Column(db.String(100), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    type_frais = db.Column(db.String(50), nullable=False)
    montant = db.Column(db.Float, nullable=False)

with app.app_context():
    db.drop_all()  # Supprime les anciennes tables obsolètes
    db.create_all()  # Recrée les tables avec la bonne structure

# Dashboard Principal
@app.route('/')
def dashboard():
    total_eleves = Eleve.query.count()
    paiements = Paiement.query.all()
    total_recettes = sum(p.montant for p in paiements)
    return render_template('dashboard.html', total_eleves=total_eleves, total_recettes=total_recettes)

# Module Inscriptions & Liste Élèves
@app.route('/eleves', methods=['GET', 'POST'])
def eleves():
    if request.method == 'POST':
        nom = request.form.get('nom_complet')
        classe = request.form.get('classe')
        telephone = request.form.get('telephone_tuteur')
        
        # Génération automatique d'un matricule
        count = Eleve.query.count() + 1
        matricule = f"CHAR-{datetime.now().year}-{count:03d}"

        nouvel_eleve = Eleve(
            nom_complet=nom,
            classe=classe,
            matricule=matricule,
            telephone_tuteur=telephone
        )
        db.session.add(nouvel_eleve)
        db.session.commit()
        return redirect(url_for('eleves'))

    liste_eleves = Eleve.query.order_by(Eleve.id.desc()).all()
    return render_template('eleves.html', eleves=liste_eleves)

# Module Paiements
@app.route('/paiements', methods=['GET', 'POST'])
def paiements():
    donnees_recu = None
    eleves_liste = Eleve.query.all()
    if request.method == 'POST':
        nom = request.form.get('nom_eleve')
        classe = request.form.get('classe')
        type_frais = request.form.get('type_frais')
        montant = float(request.form.get('montant', 0))
        date_heure = datetime.now().strftime("%d/%m/%Y %H:%M")

        nouveau = Paiement(
            date_heure=date_heure,
            nom_eleve=nom,
            classe=classe,
            type_frais=type_frais,
            montant=montant
        )
        db.session.add(nouveau)
        db.session.commit()

        donnees_recu = {
            'nom': nom,
            'classe': classe,
            'type_frais': type_frais,
            'montant': montant,
            'date_heure': date_heure
        }

    return render_template('paiements.html', recu=donnees_recu, eleves=eleves_liste)

# Module Historique
@app.route('/historique')
def historique():
    liste = Paiement.query.order_by(Paiement.id.desc()).all()
    return render_template('historique.html', paiements=liste)

# Export Excel
@app.route('/download')
def download():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Paiements"
    ws.append(["N°", "Date & Heure", "Élève", "Classe", "Type de Frais", "Montant (FC)"])

    for p in Paiement.query.all():
        ws.append([p.id, p.date_heure, p.nom_eleve, p.classe, p.type_frais, p.montant])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="rapport_paiements.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == '__main__':
    app.run()
