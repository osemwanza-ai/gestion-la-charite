from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import io

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
    sections = db.Column(db.String(200), default="Toutes")
    options = db.Column(db.String(200), default="Toutes")

class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(20), unique=True, nullable=False)
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

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    try:
        frais = FraisInscription.query.first()
    except Exception:
        frais = None
    
    if request.method == 'POST':
        if not frais:
            flash("⚠️ L'inscription est bloquée : les frais n'ont pas été configurés.", "danger")
            return redirect(url_for('inscription'))

        # Génération dynamique du matricule (Format Ex: CH-2026-001)
        annee_en_cours = datetime.now().year
        dernier_eleve = Eleve.query.order_by(Eleve.id.desc()).first()
        suivant_id = (dernier_eleve.id + 1) if dernier_eleve else 1
        nouveau_matricule = f"CH-{annee_en_cours}-{suivant_id:03d}"

        nouveau_eleve = Eleve(
            matricule=nouveau_matricule,
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

        flash(f"✅ Élève inscrit avec succès ! Matricule attribué : {nouveau_matricule}", "success")
        return redirect(url_for('index'))

    return render_template('inscription.html', frais=frais)

@app.route('/admin', methods=['GET', 'POST'])
@app.route('/frais', methods=['GET', 'POST'])
def admin():
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
            sections_list = request.form.getlist('sections')
            options_list = request.form.getlist('options')
            
            sections_str = ", ".join(sections_list) if sections_list else "Toutes"
            options_str = ", ".join(options_list) if options_list else "Toutes"

            nouvelle_rubrique = RubriqueFrais(
                nom=nom, 
                montant=montant,
                sections=sections_str,
                options=options_str
            )
            db.session.add(nouvelle_rubrique)
            db.session.commit()
            flash("✅ Rubrique de frais enregistrée avec succès.", "success")

        elif action == 'modifier_rubrique':
            rubrique_id = request.form.get('rubrique_id')
            rubrique = RubriqueFrais.query.get_or_404(rubrique_id)
            
            rubrique.nom = request.form.get('nom')
            rubrique.montant = float(request.form.get('montant'))
            db.session.commit()
            flash("✏️ Rubrique modifiée avec succès.", "info")

        elif action == 'supprimer_rubrique':
            rubrique_id = request.form.get('rubrique_id')
            rubrique = RubriqueFrais.query.get_or_404(rubrique_id)
            db.session.delete(rubrique)
            db.session.commit()
            flash("🗑️ Rubrique supprimée.", "warning")

        return redirect(url_for('admin'))

    try:
        frais_inscription = FraisInscription.query.first()
        rubriques = RubriqueFrais.query.all()
    except Exception:
        frais_inscription = None
        rubriques = []
        
    return render_template('admin.html', frais_inscription=frais_inscription, rubriques=rubriques)

# ROUTE PERCEPTION DES FRAIS
@app.route('/paiement', methods=['GET', 'POST'])
@app.route('/paiement/<int:eleve_id>', methods=['GET', 'POST'])
@app.route('/payer', methods=['GET', 'POST'])
@app.route('/payer/<int:eleve_id>', methods=['GET', 'POST'])
def paiement(eleve_id=None):
    eleves = Eleve.query.order_by(Eleve.nom_complet.asc()).all()
    eleve_selectionne = Eleve.query.get(eleve_id) if eleve_id else None
    rubriques = RubriqueFrais.query.all()
    
    if request.method == 'POST':
        selected_id = request.form.get('eleve_id')
        if selected_id and not request.form.get('rubrique_id'):
            return redirect(url_for('paiement', eleve_id=selected_id))

        if eleve_selectionne:
            rubrique_id = request.form.get('rubrique_id')
            trimestre = request.form.get('trimestre')
            montant_verse = float(request.form.get('montant'))
            
            rubrique = RubriqueFrais.query.get(rubrique_id)
            montant_fixe = rubrique.montant

            paiements_existants = Paiement.query.filter_by(
                eleve_id=eleve_selectionne.id, 
                rubrique_id=rubrique_id, 
                trimestre=trimestre
            ).all()
            
            total_deja_paye = sum(p.montant for p in paiements_existants)
            reste_a_payer = montant_fixe - total_deja_paye

            if reste_a_payer <= 0:
                flash(f"⚠️ Le solde pour {rubrique.nom} ({trimestre}) est déjà apuré.", "danger")
                return redirect(url_for('paiement', eleve_id=eleve_selectionne.id))

            if montant_verse > reste_a_payer:
                flash(f"⚠️ Le montant dépasse le solde du {trimestre} ({reste_a_payer:,.0f} FC restant).", "warning")
                return redirect(url_for('paiement', eleve_id=eleve_selectionne.id))

            nouveau_paiement = Paiement(
                eleve_id=eleve_selectionne.id,
                rubrique_id=rubrique_id,
                trimestre=trimestre,
                montant=montant_verse,
                date_paiement=datetime.now()
            )
            db.session.add(nouveau_paiement)
            db.session.commit()

            flash(f"✅ Paiement de {montant_verse:,.0f} FC enregistré pour {eleve_selectionne.nom_complet}.", "success")
            return redirect(url_for('rapports'))

    return render_template('paiement.html', eleve=eleve_selectionne, eleves=eleves, rubriques=rubriques)

# ROUTE AFFICHAGE DES RAPPORTS COMPTABLES
@app.route('/rapports')
def rapports():
    type_rapport = request.args.get('type', 'tous')
    query = Paiement.query

    if type_rapport == 'minerval':
        query = query.join(RubriqueFrais).filter(RubriqueFrais.nom.ilike('%minerval%'))
    elif type_rapport == 'connexes' or type_rapport == 'technique':
        query = query.join(RubriqueFrais).filter(~RubriqueFrais.nom.ilike('%minerval%'), ~RubriqueFrais.nom.ilike('%inscription%'))

    paiements_filtrés = query.order_by(Paiement.date_paiement.desc()).all()
    total_encaisse = sum(p.montant for p in paiements_filtrés)

    return render_template('rapports.html', paiements=paiements_filtrés, total=total_encaisse, type_actuel=type_rapport)

# ROUTE TÉLÉCHARGEMENT EXPORTATION EXCEL/CSV (Résout l'erreur 404)
@app.route('/download/<type_rapport>')
def download_rapport(type_rapport):
    try:
        output = io.StringIO()
        output.write("Matricule;Nom Complet;Rubrique;Trimestre;Montant (FC);Date\n")

        query = Paiement.query
        if type_rapport in ['technique', 'connexes']:
            query = query.join(RubriqueFrais).filter(~RubriqueFrais.nom.ilike('%minerval%'), ~RubriqueFrais.nom.ilike('%inscription%'))
        elif type_rapport == 'minerval':
            query = query.join(RubriqueFrais).filter(RubriqueFrais.nom.ilike('%minerval%'))

        paiements = query.all()
        for p in paiements:
            output.write(f"{p.eleve.matricule};{p.eleve.nom_complet};{p.rubrique.nom};{p.trimestre};{p.montant};{p.date_paiement.strftime('%d/%m/%Y')}\n")

        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8-sig'))
        mem.seek(0)

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'rapport_{type_rapport}.csv'
        )
    except Exception as e:
        flash(f"⚠️ Erreur lors de la génération du fichier : {str(e)}", "danger")
        return redirect(url_for('rapports'))

if __name__ == '__main__':
    app.run(debug=True)
