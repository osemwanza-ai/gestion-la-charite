from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# --- 1. INITIALISATION DE L'APPLICATION ---
app = Flask(__name__)
app.secret_key = "cle_secrete_complexe_la_charite"

# --- 2. CONFIGURATION DE LA BASE DE DONNÉES ---
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

# --- 3. MODÈLES DE DONNÉES ---
class FraisInscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    montant = db.Column(db.Float, nullable=False)

class RubriqueFrais(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Float, nullable=False)

class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    sexe = db.Column(db.String(10), nullable=False)
    date_naissance = db.Column(db.String(20))
    lieu_naissance = db.Column(db.String(100))
    adresse = db.Column(db.String(200), nullable=False)
    nom_responsables = db.Column(db.String(100), nullable=False)
    lien_parente = db.Column(db.String(50), nullable=False)
    telephone_principal = db.Column(db.String(20), nullable=False)
    telephone_secondaire = db.Column(db.String(20))
    section = db.Column(db.String(50), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    option = db.Column(db.String(100))
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)
    paiements = db.relationship('Paiement', backref='eleve', lazy=True)

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleve.id'), nullable=False)
    rubrique_id = db.Column(db.Integer, db.ForeignKey('rubrique_frais.id'), nullable=False)
    trimestre = db.Column(db.String(50), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_paiement = db.Column(db.DateTime, default=datetime.utcnow)
    rubrique = db.relationship('RubriqueFrais')

# --- 4. INITIALISATION DE LA BASE ---
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Erreur DB : {e}")

# --- 5. ROUTES DE L'APPLICATION ---

@app.route('/init-db')
def init_db():
    try:
        db.drop_all()
        db.create_all()
        return "✅ Base de données réinitialisée avec succès ! <br><br><a href='/'>Retour à l'accueil</a>"
    except Exception as e:
        return f"❌ Erreur : {str(e)}"

@app.route('/')
def index():
    try:
        eleves = Eleve.query.order_by(Eleve.date_inscription.desc()).all()
        return render_template('dashboard.html', eleves=eleves)
    except Exception:
        return render_template('dashboard.html', eleves=[])

@app.route('/eleves')
def liste_eleves():
    eleves = Eleve.query.order_by(Eleve.date_inscription.desc()).all()
    return render_template('eleves.html', eleves=eleves)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/paiements')
def paiements():
    paiements_liste = Paiement.query.order_by(Paiement.date_paiement.desc()).all()
    return render_template('paiements.html', paiements=paiements_liste)

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    try:
        frais = FraisInscription.query.first()
    except Exception:
        frais = None
    
    if request.method == 'POST':
        if not frais:
            flash("⚠️ L'inscription est bloquée : les frais d'inscription n'ont pas encore été configurés.", "danger")
            return redirect(url_for('inscription'))

        nouveau_eleve = Eleve(
            nom_complet=request.form.get('nom_complet'),
            sexe=request.form.get('sexe'),
            date_naissance=request.form.get('date_naissance'),
            lieu_naissance=request.form.get('lieu_naissance'),
            adresse=request.form.get('adresse'),
            nom_responsables=request.form.get('nom_responsables'),
            lien_parente=request.form.get('lien_parente'),
            telephone_principal=request.form.get('telephone_principal'),
            telephone_secondaire=request.form.get('telephone_secondaire'),
            section=request.form.get('section'),
            classe=request.form.get('classe'),
            option=request.form.get('option')
        )
        db.session.add(nouveau_eleve)
        db.session.commit()

        flash("✅ Élève inscrit avec succès !", "success")
        return redirect(url_for('index'))

    return render_template('inscription.html', frais=frais)

@app.route('/frais', methods=['GET', 'POST'])
def frais():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'frais_inscription':
            montant = float(request.form.get('montant'))
            frais_obj = FraisInscription.query.first()
            if frais_obj:
                frais_obj.montant = montant
            else:
                frais_obj = FraisInscription(montant=montant)
                db.session.add(frais_obj)
            db.session.commit()
            flash("Frais d'inscription mis à jour.", "success")
            
        elif action == 'ajouter_rubrique':
            nom = request.form.get('nom')
            montant = float(request.form.get('montant'))
            nouvelle_rubrique = RubriqueFrais(nom=nom, montant=montant)
            db.session.add(nouvelle_rubrique)
            db.session.commit()
            flash("Rubrique de frais ajoutée.", "success")

        return redirect(url_for('frais'))

    try:
        frais_inscription = FraisInscription.query.first()
        rubriques = RubriqueFrais.query.all()
    except Exception:
        frais_inscription = None
        rubriques = []
        
    return render_template('frais.html', frais_inscription=frais_inscription, rubriques=rubriques)

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

        paiements_existants = Paiement.query.filter_by(
            eleve_id=eleve.id, 
            rubrique_id=rubrique_id, 
            trimestre=trimestre
        ).all()
        
        total_deja_paye = sum(p.montant for p in paiements_existants)
        reste_a_payer = montant_fixe - total_deja_paye

        if reste_a_payer <= 0:
            flash(f"⚠️ Le solde pour {rubrique.nom} ({trimestre}) est déjà totalement apuré (0 FC restant).", "danger")
            return redirect(url_for('payer', eleve_id=eleve.id))

        if montant_verse > reste_a_payer:
            flash(f"⚠️ Le montant saisi ({montant_verse:,.0f} FC) dépasse le solde du {trimestre}. Le reste à payer est de {reste_a_payer:,.0f} FC.", "warning")
            return redirect(url_for('payer', eleve_id=eleve.id))

        nouveau_paiement = Paiement(
            eleve_id=eleve.id,
            rubrique_id=rubrique_id,
            trimestre=trimestre,
            montant=montant_verse,
            date_paiement=datetime.now()
        )
        db.session.add(nouveau_paiement)
        db.session.commit()

        flash(f"✅ Paiement de {montant_verse:,.0f} FC enregistré.", "success")
        return redirect(url_for('index'))

    return render_template('payer.html', eleve=eleve, rubriques=rubriques)

if __name__ == '__main__':
    app.run(debug=True)
