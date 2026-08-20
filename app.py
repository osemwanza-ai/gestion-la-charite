import os
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'charite_secret_key_2026'

# Configuration dynamique : PostgreSQL en ligne, SQLite en local
database_url = os.environ.get('DATABASE_URL', 'sqlite:///charite.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODÈLES DE BASE DE DONNÉES ---

class Eleve(db.Model):
    __tablename__ = 'eleves'
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(20), unique=True, nullable=False)
    nom_complet = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(50), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    option = db.Column(db.String(50), default="SANS OPTION")
    
    paiements = db.relationship('Paiement', backref='eleve', lazy=True, cascade="all, delete-orphan")

class RubriqueFrais(db.Model):
    __tablename__ = 'rubriques_frais'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(50), nullable=False)
    classe = db.Column(db.String(50), default="Toutes")
    montant_exige_cdf = db.Column(db.Float, nullable=False)
    
    paiements = db.relationship('Paiement', backref='rubrique', lazy=True)

class Paiement(db.Model):
    __tablename__ = 'paiements'
    id = db.Column(db.Integer, primary_key=True)
    num_recu = db.Column(db.String(30), unique=True, nullable=False)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleves.id'), nullable=False)
    rubrique_id = db.Column(db.Integer, db.ForeignKey('rubriques_frais.id'), nullable=False)
    montant_paye_cdf = db.Column(db.Float, nullable=False)
    mode_paiement = db.Column(db.String(50), default="Cash")
    date_paiement = db.Column(db.DateTime, default=datetime.utcnow)

class Depense(db.Model):
    __tablename__ = 'depenses'
    id = db.Column(db.Integer, primary_key=True)
    motif = db.Column(db.String(200), nullable=False)
    categorie = db.Column(db.String(50), nullable=False)
    montant_cdf = db.Column(db.Float, nullable=False)
    date_depense = db.Column(db.DateTime, default=datetime.utcnow)

# --- INITIALISATION ET ROUTES ---

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    total_eleves = Eleve.query.count()
    recettes = db.session.query(db.func.sum(Paiement.montant_paye_cdf)).scalar() or 0.0
    depenses = db.session.query(db.func.sum(Depense.montant_cdf)).scalar() or 0.0
    solde = recettes - depenses
    
    derniers_paiements = Paiement.query.order_by(Paiement.date_paiement.desc()).limit(5).all()
    return render_template('index.html', total_eleves=total_eleves, recettes=recettes, depenses=depenses, solde=solde, derniers_paiements=derniers_paiements)

@app.route('/inscriptions', methods=['GET', 'POST'])
def inscriptions():
    if request.method == 'POST':
        nom = request.form.get('nom_complet').strip().upper()
        section = request.form.get('section')
        classe = request.form.get('classe')
        option = request.form.get('option', 'SANS OPTION')
        
        count = Eleve.query.count() + 1
        matricule = f"CSC-{datetime.now().year}-{count:04d}"
        
        nouvel_eleve = Eleve(matricule=matricule, nom_complet=nom, section=section, classe=classe, option=option)
        db.session.add(nouvel_eleve)
        db.session.commit()
        
        flash(f"Élève inscrit avec succès ! Matricule : {matricule}", "success")
        return redirect(url_for('inscriptions'))
        
    eleves = Eleve.query.order_by(Eleve.id.desc()).all()
    return render_template('inscriptions.html', eleves=eleves)

@app.route('/paiements', methods=['GET', 'POST'])
def paiements():
    if request.method == 'POST':
        eleve_id = request.form.get('eleve_id')
        rubrique_id = request.form.get('rubrique_id')
        montant_paye = request.form.get('montant_paye_cdf')
        mode_paiement = request.form.get('mode_paiement', 'Cash')
        
        if not eleve_id or not rubrique_id or not montant_paye:
            flash("Veuillez sélectionner un élève valide dans la liste déroulante.", "danger")
            return redirect(url_for('paiements'))
            
        montant_paye = float(montant_paye)
        count_p = Paiement.query.count() + 1
        num_recu = f"REC-{datetime.now().strftime('%Y%m%d')}-{count_p:04d}"
        
        nouveau_paiement = Paiement(
            num_recu=num_recu,
            eleve_id=int(eleve_id),
            rubrique_id=int(rubrique_id),
            montant_paye_cdf=montant_paye,
            mode_paiement=mode_paiement
        )
        
        db.session.add(nouveau_paiement)
        db.session.commit()
        
        flash(f"Paiement enregistré avec succès ! Reçu N° {num_recu}", "success")
        return redirect(url_for('ticket_pos', paiement_id=nouveau_paiement.id))

    eleves = Eleve.query.order_by(Eleve.nom_complet.asc()).all()
    paiements_recents = Paiement.query.order_by(Paiement.date_paiement.desc()).limit(10).all()
    return render_template('paiements.html', eleves=eleves, paiements=paiements_recents)

@app.route('/api/eleve_info/<int:eleve_id>')
def api_eleve_info(eleve_id):
    eleve = Eleve.query.get_or_404(eleve_id)
    rubriques = RubriqueFrais.query.filter(
        (RubriqueFrais.section == eleve.section) & 
        ((RubriqueFrais.classe == 'Toutes') | (RubriqueFrais.classe == eleve.classe))
    ).all()
    
    rubriques_data = []
    for r in rubriques:
        deja_paye = db.session.query(db.func.sum(Paiement.montant_paye_cdf)).filter(
            Paiement.eleve_id == eleve.id,
            Paiement.rubrique_id == r.id
        ).scalar() or 0.0
        
        solde_restant = r.montant_exige_cdf - deja_paye
        
        rubriques_data.append({
            'id': r.id,
            'nom': r.nom,
            'total_exige': r.montant_exige_cdf,
            'deja_paye': deja_paye,
            'solde_restant': max(0.0, solde_restant)
        })
        
    return jsonify({
        'id': eleve.id,
        'nom_complet': eleve.nom_complet,
        'section': eleve.section,
        'classe': eleve.classe,
        'option': eleve.option,
        'rubriques': rubriques_data
    })

@app.route('/admin_frais', methods=['GET', 'POST'])
def admin_frais():
    if request.method == 'POST':
        nom = request.form.get('nom')
        section = request.form.get('section')
        classe = request.form.get('classe', 'Toutes')
        montant = float(request.form.get('montant_exige_cdf'))
        
        nouvelle_rubrique = RubriqueFrais(nom=nom, section=section, classe=classe, montant_exige_cdf=montant)
        db.session.add(nouvelle_rubrique)
        db.session.commit()
        
        flash("Rubrique de frais ajoutée.", "success")
        return redirect(url_for('admin_frais'))
        
    rubriques = RubriqueFrais.query.all()
    return render_template('admin_frais.html', rubriques=rubriques)

@app.route('/comptabilite', methods=['GET', 'POST'])
def comptabilite():
    if request.method == 'POST':
        motif = request.form.get('motif')
        categorie = request.form.get('categorie')
        montant = float(request.form.get('montant_cdf'))
        
        nouvelle_depense = Depense(motif=motif, categorie=categorie, montant_cdf=montant)
        db.session.add(nouvelle_depense)
        db.session.commit()
        
        flash("Dépense enregistrée.", "warning")
        return redirect(url_for('comptabilite'))
        
    depenses = Depense.query.order_by(Depense.date_depense.desc()).all()
    total_depenses = sum(d.montant_cdf for d in depenses)
    return render_template('comptabilite.html', depenses=depenses, total_depenses=total_depenses)

@app.route('/ticket_pos/<int:paiement_id>')
def ticket_pos(paiement_id):
    paiement = Paiement.query.get_or_404(paiement_id)
    return render_template('ticket_pos.html', p=paiement)

@app.route('/seed')
def seed():
    db.create_all()
    
    if RubriqueFrais.query.count() == 0:
        r1 = RubriqueFrais(nom="Frais de Scolarité T1", section="Maternelle", classe="Toutes", montant_exige_cdf=150000)
        r2 = RubriqueFrais(nom="Frais de Scolarité T1", section="Primaire", classe="Toutes", montant_exige_cdf=180000)
        r3 = RubriqueFrais(nom="Frais de Scolarité T1", section="Secondaire", classe="Toutes", montant_exige_cdf=220000)
        r4 = RubriqueFrais(nom="Frais d'Achat Uniforme", section="Primaire", classe="Toutes", montant_exige_cdf=45000)
        db.session.add_all([r1, r2, r3, r4])
        db.session.commit()
        
    return "Base de données initialisée avec succès sur PostgreSQL/SQLite !"

if __name__ == '__main__':
    app.run(debug=True)
