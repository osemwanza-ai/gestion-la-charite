from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import openpyxl
from io import BytesIO
from datetime import datetime
import os

# --- 1. INITIALISATION DE L'APPLICATION ---
app = Flask(__name__)
app.secret_key = "cle_secrete_complexe_la_charite"

# --- 2. CONFIGURATION BASE DE DONNÉES SÉCURISÉE ---
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'app_database.db')}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 3. MODÈLES DE DONNÉES (EXEMPLES DE STRUCTURE) ---
class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(50), nullable=False)
    classe = db.Column(db.String(50), nullable=False)

class RubriqueFrais(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Float, nullable=False)

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleve.id'), nullable=False)
    rubrique_id = db.Column(db.Integer, db.ForeignKey('rubrique_frais.id'), nullable=False)
    trimestre = db.Column(db.String(50), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_paiement = db.Column(db.DateTime, default=datetime.utcnow)

# Création automatique des tables
with app.app_context():
    db.create_all()

# --- 4. ROUTES DE L'APPLICATION ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/payer/<int:eleve_id>', methods=['GET', 'POST'])
def payer(eleve_id):
    eleve = Eleve.query.get_or_404(eleve_id)
    rubriques = RubriqueFrais.query.all()
    
    if request.method == 'POST':
        rubrique_id = request.form.get('rubrique_id')
        trimestre = request.form.get('trimestre')
        montant_verse = float(request.form.get('montant'))
        
        rubrique = RubriqueFrais.query.get(rubrique_id)
        montant_fixe = rubrique.montant

        # Verification des paiements deja effectues
        paiements_existants = Paiement.query.filter_by(
            eleve_id=eleve.id, 
            rubrique_id=rubrique_id, 
            trimestre=trimestre
        ).all()
        
        total_deja_paye = sum(p.montant for p in paiements_existants)
        reste_a_payer = montant_fixe - total_deja_paye

        # Restrictions et controles du solde
        if reste_a_payer <= 0:
            flash(f"⚠️ Le solde pour {rubrique.nom} ({trimestre}) est déjà totalement apuré (0 FC restant). Veuillez sélectionner le trimestre suivant.", "danger")
            return redirect(url_for('payer', eleve_id=eleve.id))

        if montant_verse > reste_a_payer:
            flash(f"⚠️ Le montant saisi ({montant_verse:,.0f} FC) dépasse le solde du {trimestre}. Le reste à payer est de {reste_a_payer:,.0f} FC.", "warning")
            return redirect(url_for('payer', eleve_id=eleve.id))

        # Enregistrement du paiement validé
        nouveau_paiement = Paiement(
            eleve_id=eleve.id,
            rubrique_id=rubrique_id,
            trimestre=trimestre,
            montant=montant_verse,
            date_paiement=datetime.now()
        )
        db.session.add(nouveau_paiement)
        db.session.commit()

        flash(f"✅ Paiement de {montant_verse:,.0f} FC enregistré avec succès. Reste à payer : {reste_a_payer - montant_verse:,.0f} FC.", "success")
        return redirect(url_for('payer', eleve_id=eleve.id))

    return render_template('payer.html', eleve=eleve, rubriques=rubriques)

if __name__ == '__main__':
    app.run(debug=True)
