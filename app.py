import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'charite_secret_key_2026'

# Configuration de la base de données SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'charite.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# MODÈLES DE BASE DE DONNÉES
# ==========================================

class Eleve(db.Model):
    __tablename__ = 'eleves'

    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(30), unique=True, nullable=False)
    nom_complet = db.Column(db.String(100), nullable=False)
    sexe = db.Column(db.String(10), nullable=False)
    date_naissance = db.Column(db.String(20), nullable=False)
    lieu_naissance = db.Column(db.String(100), nullable=False)
    nationalite = db.Column(db.String(50), default="Congolaise")
    adresse = db.Column(db.String(200), nullable=False)
    
    # Santé & Parcours
    groupe_sanguin = db.Column(db.String(10))
    allergies_sante = db.Column(db.Text)
    ecole_provenance = db.Column(db.String(150))
    pourcentage_obtenu = db.Column(db.String(10))

    # Parents & Tuteur
    nom_pere = db.Column(db.String(100))
    prof_pere = db.Column(db.String(100))
    tel_pere = db.Column(db.String(30))
    nom_mere = db.Column(db.String(100))
    prof_mere = db.Column(db.String(100))
    tel_mere = db.Column(db.String(30))
    nom_tuteur = db.Column(db.String(100))
    tel_tuteur = db.Column(db.String(30))
    email_responsable = db.Column(db.String(100))

    # Affectation Scolaire
    section = db.Column(db.String(30), nullable=False)
    classe = db.Column(db.String(30), nullable=False)
    option = db.Column(db.String(50))
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)

    # Relations
    paiements = db.relationship('Paiement', backref='eleve', lazy=True, cascade="all, delete-orphan")


class RubriqueFrais(db.Model):
    __tablename__ = 'rubriques_frais'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    
    paiements = db.relationship('Paiement', backref='rubrique', lazy=True)


class Paiement(db.Model):
    __tablename__ = 'paiements'

    id = db.Column(db.Integer, primary_key=True)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleves.id'), nullable=False)
    rubrique_id = db.Column(db.Integer, db.ForeignKey('rubriques_frais.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_paiement = db.Column(db.DateTime, default=datetime.utcnow)


# Création initiale des tables
with app.app_context():
    db.create_all()


# ==========================================
# ROUTES DE L'APPLICATION
# ==========================================

# 1. PAGE D'ACCUEIL / TABLEAU DE BORD
@app.route('/')
def index():
    total_eleves = Eleve.query.count()
    total_maternelle = Eleve.query.filter_by(section='Maternelle').count()
    total_primaire = Eleve.query.filter_by(section='Primaire').count()
    total_secondaire = Eleve.query.filter_by(section='EB').count()
    total_humanites = Eleve.query.filter_by(section='Humanités').count()
    
    derniers_inscrits = Eleve.query.order_by(Eleve.id.desc()).limit(5).all()

    return render_template(
        'index.html',
        total_eleves=total_eleves,
        total_maternelle=total_maternelle,
        total_primaire=total_primaire,
        total_secondaire=total_secondaire,
        total_humanités=total_humanites,
        derniers_inscrits=derniers_inscrits
    )


# 2. PAGE D'INSCRIPTION D'UN ÉLÈVE
@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    # Recherche stricte ou partielle de la rubrique dédiée aux frais d'inscription
    frais_inscription = RubriqueFrais.query.filter(RubriqueFrais.nom.ilike("%inscription%")).first()

    if request.method == 'POST':
        # BLOQUAGE DE SÉCURITÉ : Réjection du formulaire si la rubrique n'est pas définie
        if not frais_inscription:
            flash("ERREUR : Impossible d'inscrire un élève. La rubrique 'Frais d'inscription' doit d'abord être définie dans la Tarification des Frais.", "danger")
            return redirect(url_for('gestion_frais'))

        annee = datetime.now().year
        count = Eleve.query.count() + 1
        matricule = f"{annee}-CSC-{count:03d}"

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
            nom_tuteur=request.form.get('nom_tuteur'),
            tel_tuteur=request.form.get('tel_tuteur'),
            email_responsable=request.form.get('email_responsable'),
            section=request.form.get('section'),
            classe=request.form.get('classe'),
            option=request.form.get('option') if request.form.get('section') == 'Humanités' else None
        )

        db.session.add(nouvel_eleve)
        db.session.commit()

        # Enregistrement automatique du paiement d'inscription
        p_inscr = Paiement(
            eleve_id=nouvel_eleve.id,
            rubrique_id=frais_inscription.id,
            montant=frais_inscription.montant,
            date_paiement=datetime.now()
        )
        db.session.add(p_inscr)
        db.session.commit()

        flash(f"L'élève {nouvel_eleve.nom_complet} a été inscrit avec succès (Paiement d'inscription : {frais_inscription.montant}$ enregistré). Matricule : {matricule}", "success")
        return redirect(url_for('liste_eleves'))

    return render_template('inscription.html', frais_inscription=frais_inscription)


# 3. RÉPERTOIRE GÉNÉRAL DES ÉLÈVES
@app.route('/eleves')
def liste_eleves():
    nom_filter = request.args.get('nom', '').strip()
    section_filter = request.args.get('section', '')
    classe_filter = request.args.get('classe', '').strip()

    query = Eleve.query

    if nom_filter:
        query = query.filter(Eleve.nom_complet.ilike(f"%{nom_filter}%"))
    if section_filter:
        query = query.filter(Eleve.section == section_filter)
    if classe_filter:
        query = query.filter(Eleve.classe.ilike(f"%{classe_filter}%"))

    eleves_db = query.order_by(Eleve.nom_complet.asc()).all()

    total_eleves = Eleve.query.count()
    total_garcons = Eleve.query.filter_by(sexe='M').count()
    total_filles = Eleve.query.filter_by(sexe='F').count()

    rubriques = RubriqueFrais.query.all()
    rubriques_scolaires = [r for r in rubriques if 'inscription' not in r.nom.lower()]

    eleves_data = []
    for e in eleves_db:
        frais_detail = []
        for r in rubriques_scolaires:
            paye = sum(p.montant for p in e.paiements if p.rubrique_id == r.id)
            solde = max(0.0, r.montant - paye)
            frais_detail.append({
                'nom': r.nom,
                'montant_du': r.montant,
                'montant_paye': paye,
                'solde': solde
            })

        eleves_data.append({
            'obj': e,
            'frais_detail': frais_detail
        })

    return render_template(
        'eleves.html',
        eleves_data=eleves_data,
        total_eleves=total_eleves,
        total_garcons=total_garcons,
        total_filles=total_filles,
        nom_sel=nom_filter,
        section_sel=section_filter,
        classe_sel=classe_filter
    )


# 4. GESTION DES FRAIS & CONFIGURATION
@app.route('/frais', methods=['GET', 'POST'])
def gestion_frais():
    if request.method == 'POST':
        nom = request.form.get('nom')
        montant = float(request.form.get('montant', 0))
        description = request.form.get('description')

        nouvelle_rubrique = RubriqueFrais(nom=nom, montant=montant, description=description)
        db.session.add(nouvelle_rubrique)
        db.session.commit()
        flash("Nouvelle rubrique de frais ajoutée avec succès !", "success")
        return redirect(url_for('gestion_frais'))

    rubriques = RubriqueFrais.query.all()
    return render_template('frais.html', rubriques=rubriques)


if __name__ == '__main__':
    app.run(debug=True)
