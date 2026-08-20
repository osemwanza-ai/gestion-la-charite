import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'la_charite_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecole.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# MODÈLES DE BASE DE DONNÉES
# ==========================================

class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(30), unique=True, nullable=False)
    nom_complet = db.Column(db.String(100), nullable=False)
    sexe = db.Column(db.String(10), nullable=False)
    date_naissance = db.Column(db.String(20))
    lieu_naissance = db.Column(db.String(50))
    nationalite = db.Column(db.String(50), default="Congolaise")
    adresse = db.Column(db.Text)
    groupe_sanguin = db.Column(db.String(10))
    allergies_sante = db.Column(db.Text)
    ecole_provenance = db.Column(db.String(100))
    pourcentage_obtenu = db.Column(db.String(10))
    nom_pere = db.Column(db.String(100))
    prof_pere = db.Column(db.String(100))
    tel_pere = db.Column(db.String(30))
    nom_mere = db.Column(db.String(100))
    prof_mere = db.Column(db.String(100))
    tel_mere = db.Column(db.String(30))
    section = db.Column(db.String(50), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    option = db.Column(db.String(50), default="N/A")
    date_inscription = db.Column(db.DateTime, default=datetime.now)

    paiements = db.relationship('Paiement', backref='eleve', lazy=True, cascade="all, delete-orphan")

class RubriqueFrais(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)

    paiements = db.relationship('Paiement', backref='rubrique', lazy=True)

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_recu = db.Column(db.String(30), unique=True)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleve.id'), nullable=False)
    rubrique_id = db.Column(db.Integer, db.ForeignKey('rubrique_frais.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    mode_paiement = db.Column(db.String(50), default="Cash")
    reference_bordereau = db.Column(db.String(50))
    date_paiement = db.Column(db.DateTime, default=datetime.now)

# ==========================================
# ROUTES PRINCIPALES
# ==========================================

@app.route('/')
def index():
    total_eleves = Eleve.query.count()
    total_rubriques = RubriqueFrais.query.count()
    derniers_eleves = Eleve.query.order_by(Eleve.id.desc()).limit(5).all()
    return render_template('index.html', total_eleves=total_eleves, total_rubriques=total_rubriques, derniers_eleves=derniers_eleves)

@app.route('/inscriptions', methods=['GET', 'POST'])
def inscriptions():
    if request.method == 'POST':
        count = Eleve.query.count() + 1
        matricule = f"2026-CSC-{count:03d}"
        
        nouvel_eleve = Eleve(
            matricule=matricule,
            nom_complet=request.form.get('nom_complet'),
            sexe=request.form.get('sexe'),
            date_naissance=request.form.get('date_naissance'),
            lieu_naissance=request.form.get('lieu_naissance'),
            nationalite=request.form.get('nationalite', 'Congolaise'),
            adresse=request.form.get('adresse'),
            groupe_sanguin=request.form.get('groupe_sanguin'),
            allergies_sante=request.form.get('allergies_sante'),
            ecole_provenance=request.form.get('ecole_provenance'),
            pourcentage_obtenu=request.form.get('pourcentage_obtenu'),
            nom_pere=request.form.get('nom_pere'),
            prof_pere=request.form.get('prof_pere'),
            tel_pere=request.form.get('tel_pere'),
            nom_mere=request.form.get('nom_mere'),
            prof_mere=request.form.get('prof_mere'),
            tel_mere=request.form.get('tel_mere'),
            section=request.form.get('section'),
            classe=request.form.get('classe'),
            option=request.form.get('option', 'N/A')
        )
        db.session.add(nouvel_eleve)
        db.session.commit()
        flash(f"Élève inscrit avec succès ! Matricule attribué : {matricule}", "success")
        return redirect(url_for('inscriptions'))

    eleves = Eleve.query.order_by(Eleve.id.desc()).all()
    return render_template('inscriptions.html', eleves=eleves)

# ==========================================
# MODULE PAIEMENT DE FRAIS SCOLAIRES
# ==========================================

@app.route('/paiements', methods=['GET', 'POST'])
def paiements():
    if request.method == 'POST':
        eleve_id = request.form.get('eleve_id')
        rubrique_id = request.form.get('rubrique_id')
        montant = float(request.form.get('montant'))
        mode = request.form.get('mode_paiement')
        ref = request.form.get('reference_bordereau')

        count = Paiement.query.count() + 1
        num_recu = f"REC-2026-{count:04d}"

        nouveau_paiement = Paiement(
            numero_recu=num_recu,
            eleve_id=eleve_id,
            rubrique_id=rubrique_id,
            montant=montant,
            mode_paiement=mode,
            reference_bordereau=ref
        )
        db.session.add(nouveau_paiement)
        db.session.commit()
        flash(f"Paiement enregistré avec succès ! Reçu N° {num_recu}", "success")
        return redirect(url_for('paiements'))

    rubriques_admin = RubriqueFrais.query.filter(RubriqueFrais.nom.notilike("%inscription%")).all()
    eleves = Eleve.query.order_by(Eleve.nom_complet).all()
    historique_paiements = Paiement.query.order_by(Paiement.id.desc()).all()

    soldes = {}
    for el in eleves:
        soldes[el.id] = {}
        for rub in rubriques_admin:
            total_paye = db.session.query(db.func.sum(Paiement.montant)).filter(
                Paiement.eleve_id == el.id, 
                Paiement.rubrique_id == rub.id
            ).scalar() or 0.0
            soldes[el.id][rub.id] = {
                'paye': total_paye,
                'reste': max(0.0, rub.montant - total_paye)
            }

    # Conversion sécurisée en JSON ici
    return render_template('paiements.html', 
                           eleves=eleves, 
                           rubriques=rubriques_admin, 
                           paiements=historique_paiements,
                           soldes=json.dumps(soldes))

# ==========================================
# ROUTE DE REMPLISSAGE RAPIDE (DONNÉES TEST)
# ==========================================

@app.route('/seed')
def seed_data():
    db.drop_all()
    db.create_all()

    r_inscr = RubriqueFrais(nom="Frais d'inscription", montant=50.0, description="Admission obligatoire")
    r_t1 = RubriqueFrais(nom="Minerval - 1er Trimestre", montant=150.0, description="Scolarité T1")
    r_t2 = RubriqueFrais(nom="Minerval - 2ème Trimestre", montant=150.0, description="Scolarité T2")
    r_tech = RubriqueFrais(nom="Frais Techniques & Labo", montant=30.0, description="Matériel informatique")
    r_bulletin = RubriqueFrais(nom="Frais de Bulletin", montant=10.0, description="Édition bulletins")

    db.session.add_all([r_inscr, r_t1, r_t2, r_tech, r_bulletin])
    db.session.commit()

    e1 = Eleve(matricule="2026-CSC-001", nom_complet="KABANGA MPOYI Christian", sexe="M", date_naissance="2019-04-12", lieu_naissance="Kinshasa", adresse="Av. Lukusa N° 45, Gombe", nom_pere="KABANGA Joseph", tel_pere="+243810000001", section="Maternelle", classe="3ème Maternelle")
    e2 = Eleve(matricule="2026-CSC-002", nom_complet="NDAYA KASONGO Grace", sexe="F", date_naissance="2016-08-20", lieu_naissance="Lubumbashi", adresse="Av. Kasa-Vubu N° 102, Ngiri-Ngiri", nom_pere="KASONGO Alain", tel_pere="+243810000002", section="Primaire", classe="4ème Primaire")
    e3 = Eleve(matricule="2026-CSC-003", nom_complet="MUKENDI MUTOMBO Daniel", sexe="M", date_naissance="2012-01-15", lieu_naissance="Kinshasa", adresse="Av. Université N° 88, Makala", nom_pere="MUTOMBO Pierre", tel_pere="+243810000003", section="EB", classe="8ème EB")
    e4 = Eleve(matricule="2026-CSC-004", nom_complet="TSHIBOLA LUKUSA Esther", sexe="F", date_naissance="2009-11-05", lieu_naissance="Mbuji-Mayi", adresse="Av. Huileries N° 14, Lingwala", nom_pere="LUKUSA François", tel_pere="+243810000004", section="Humanités", classe="3ème Humanités", option="Commerciale & Gestion")

    db.session.add_all([e1, e2, e3, e4])
    db.session.commit()

    p1 = Paiement(numero_recu="REC-2026-0001", eleve_id=e1.id, rubrique_id=r_t1.id, montant=150.0, mode_paiement="Cash")
    p2 = Paiement(numero_recu="REC-2026-0002", eleve_id=e2.id, rubrique_id=r_t1.id, montant=100.0, mode_paiement="Cash")
    p3 = Paiement(numero_recu="REC-2026-0003", eleve_id=e4.id, rubrique_id=r_tech.id, montant=30.0, mode_paiement="Mobile Money")

    db.session.add_all([p1, p2, p3])
    db.session.commit()

    flash("Base de données initialisée avec succès avec des données de test !", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
