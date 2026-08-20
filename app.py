import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'charite_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///charite.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== MODÈLES ====================

class ConfigurationQuota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pct_salaires = db.Column(db.Float, default=45.0)
    pct_fonctionnement = db.Column(db.Float, default=25.0)
    pct_promoteur = db.Column(db.Float, default=15.0)
    pct_materiel = db.Column(db.Float, default=10.0)
    pct_reserve = db.Column(db.Float, default=5.0)

class RubriqueFrais(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    montant_cdf = db.Column(db.Float, nullable=False, default=0.0)
    montant = db.Column(db.Float, nullable=True, default=0.0)
    description = db.Column(db.String(255))
    sections_cibles = db.Column(db.String(255), default='Toutes')
    options_cibles = db.Column(db.String(255), default='Toutes')
    est_minerval = db.Column(db.Boolean, default=False)
    est_inscription = db.Column(db.Boolean, default=False)

class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(50), unique=True, nullable=False)
    
    # 1. Identité Élève
    nom_complet = db.Column(db.String(150), nullable=False)
    sexe = db.Column(db.String(10), nullable=False)
    date_naissance = db.Column(db.String(20))
    lieu_naissance = db.Column(db.String(100))
    nationalite = db.Column(db.String(50), default='Congolaise')
    adresse = db.Column(db.String(200))
    groupe_sanguin = db.Column(db.String(10))
    allergies_sante = db.Column(db.String(255))
    
    # 2. Scolarité demandée
    section = db.Column(db.String(50), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    option = db.Column(db.String(50))
    
    # 3. Parcours Précédent
    ecole_provenance = db.Column(db.String(150))
    pourcentage_obtenu = db.Column(db.String(10))
    
    # 4. Père (Tuteur 1)
    nom_pere = db.Column(db.String(100))
    prof_pere = db.Column(db.String(100))
    tel_pere = db.Column(db.String(20))
    tel_pere_wa = db.Column(db.String(20))
    email_pere = db.Column(db.String(100))
    
    # 5. Mère (Tuteur 2)
    nom_mere = db.Column(db.String(100))
    prof_mere = db.Column(db.String(100))
    tel_mere = db.Column(db.String(20))
    tel_mere_wa = db.Column(db.String(20))
    email_mere = db.Column(db.String(100))
    
    # 6. Urgence & Responsable
    contact_urgence_nom = db.Column(db.String(100))
    contact_urgence_lien = db.Column(db.String(50))
    contact_urgence_tel = db.Column(db.String(20))
    responsable_financier = db.Column(db.String(50))
    
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)
    paiements = db.relationship('Paiement', backref='eleve', lazy=True, cascade="all, delete-orphan")

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    num_recu = db.Column(db.String(50), unique=True, nullable=False)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleve.id'), nullable=False)
    rubrique_id = db.Column(db.Integer, db.ForeignKey('rubrique_frais.id'), nullable=False)
    montant_paye_cdf = db.Column(db.Float, nullable=False, default=0.0)
    montant_paye = db.Column(db.Float, nullable=True, default=0.0)
    mode_paiement = db.Column(db.String(50), default='Cash')
    date_paiement = db.Column(db.DateTime, default=datetime.utcnow)
    rubrique = db.relationship('RubriqueFrais')

# ==================== ROUTES ====================

@app.route('/')
def index():
    total_eleves = Eleve.query.count()
    paiements = Paiement.query.all()
    total_encaisse = sum(p.montant_paye_cdf for p in paiements)
    derniers_paiements = Paiement.query.order_by(Paiement.date_paiement.desc()).limit(5).all()
    derniers_eleves = Eleve.query.order_by(Eleve.date_inscription.desc()).limit(5).all()
    return render_template('index.html', 
                           total_eleves=total_eleves, 
                           total_encaisse=total_encaisse,
                           derniers_paiements=derniers_paiements,
                           derniers_eleves=derniers_eleves)

@app.route('/admin_frais', methods=['GET', 'POST'])
@app.route('/admin', methods=['GET', 'POST'])
def admin_frais():
    if request.method == 'POST':
        nom = request.form.get('nom')
        montant_cdf = float(request.form.get('montant_cdf', request.form.get('montant', 0)))
        description = request.form.get('description')
        sections_choisies = request.form.getlist('sections')
        options_choisies = request.form.getlist('options')
        
        str_sections = ", ".join(sections_choisies) if sections_choisies else "Toutes"
        str_options = ", ".join(options_choisies) if options_choisies else "Toutes"
        
        est_minerval = 'est_minerval' in request.form
        est_inscription = 'est_inscription' in request.form
        
        if est_inscription:
            RubriqueFrais.query.filter_by(est_inscription=True).update({'est_inscription': False})

        nouvelle_rubrique = RubriqueFrais(
            nom=nom, 
            montant_cdf=montant_cdf,
            montant=montant_cdf,
            description=description,
            sections_cibles=str_sections,
            options_cibles=str_options,
            est_minerval=est_minerval,
            est_inscription=est_inscription
        )
        db.session.add(nouvelle_rubrique)
        db.session.commit()
        flash('Rubrique enregistrée avec succès !', 'success')
        return redirect(url_for('admin_frais'))
        
    rubriques = RubriqueFrais.query.all()
    return render_template('admin.html', rubriques=rubriques, frais=rubriques)

def admin():
    return admin_frais()

@app.route('/modifier_rubrique/<int:id>', methods=['POST'])
def modifier_rubrique(id):
    rubrique = RubriqueFrais.query.get_or_404(id)
    rubrique.nom = request.form.get('nom')
    montant_val = float(request.form.get('montant_cdf', 0))
    rubrique.montant_cdf = montant_val
    rubrique.montant = montant_val
    rubrique.description = request.form.get('description')
    
    sections_choisies = request.form.getlist('sections')
    options_choisies = request.form.getlist('options')
    
    rubrique.sections_cibles = ", ".join(sections_choisies) if sections_choisies else "Toutes"
    rubrique.options_cibles = ", ".join(options_choisies) if options_choisies else "Toutes"
    
    est_inscr = 'est_inscription' in request.form
    if est_inscr and not rubrique.est_inscription:
        RubriqueFrais.query.filter_by(est_inscription=True).update({'est_inscription': False})
    
    rubrique.est_inscription = est_inscr
    rubrique.est_minerval = 'est_minerval' in request.form
    
    db.session.commit()
    flash(f'Rubrique "{rubrique.nom}" mise à jour avec succès !', 'success')
    return redirect(url_for('admin_frais'))

@app.route('/supprimer_rubrique/<int:id>', methods=['POST'])
def supprimer_rubrique(id):
    rubrique = RubriqueFrais.query.get_or_404(id)
    db.session.delete(rubrique)
    db.session.commit()
    flash('Rubrique supprimée avec succès !', 'info')
    return redirect(url_for('admin_frais'))

@app.route('/inscriptions', methods=['GET', 'POST'])
@app.route('/inscription', methods=['GET', 'POST'])
def inscriptions():
    rubrique_inscr = RubriqueFrais.query.filter_by(est_inscription=True).first()
    
    if request.method == 'POST':
        section = request.form.get('section')
        option = request.form.get('option')
        
        # Validation serveur : Obligation de l'option en Humanité
        if section == 'Humanité' and not option:
            flash("L'option est obligatoire pour l'inscription en Humanité.", "danger")
            eleves = Eleve.query.order_by(Eleve.date_inscription.desc()).all()
            return render_template('inscription.html', eleves=eleves, rubrique_inscr=rubrique_inscr, rubrique=rubrique_inscr)

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
            
            section=section,
            classe=request.form.get('classe'),
            option=option if section == 'Humanité' else None,
            
            ecole_provenance=request.form.get('ecole_provenance'),
            pourcentage_obtenu=request.form.get('pourcentage_obtenu'),
            
            nom_pere=request.form.get('nom_pere'),
            prof_pere=request.form.get('prof_pere'),
            tel_pere=request.form.get('tel_pere'),
            tel_pere_wa=request.form.get('tel_pere_wa'),
            email_pere=request.form.get('email_pere'),
            
            nom_mere=request.form.get('nom_mere'),
            prof_mere=request.form.get('prof_mere'),
            tel_mere=request.form.get('tel_mere'),
            tel_mere_wa=request.form.get('tel_mere_wa'),
            email_mere=request.form.get('email_mere'),
            
            contact_urgence_nom=request.form.get('contact_urgence_nom'),
            contact_urgence_lien=request.form.get('contact_urgence_lien'),
            contact_urgence_tel=request.form.get('contact_urgence_tel'),
            responsable_financier=request.form.get('responsable_financier')
        )
        db.session.add(nouvel_eleve)
        db.session.commit()
        
        if rubrique_inscr:
            num_recu = f"REC-INS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            p_inscr = Paiement(
                num_recu=num_recu,
                eleve_id=nouvel_eleve.id,
                rubrique_id=rubrique_inscr.id,
                montant_paye_cdf=rubrique_inscr.montant_cdf,
                montant_paye=rubrique_inscr.montant_cdf,
                mode_paiement='Cash'
            )
            db.session.add(p_inscr)
            db.session.commit()

        flash(f'Élève {nouvel_eleve.nom_complet} inscrit avec succès !', 'success')
        return redirect(url_for('inscriptions'))
        
    eleves = Eleve.query.order_by(Eleve.date_inscription.desc()).all()
    return render_template('inscription.html', eleves=eleves, rubrique_inscr=rubrique_inscr, rubrique=rubrique_inscr)

def inscription():
    return inscriptions()

@app.route('/paiements', methods=['GET', 'POST'])
def paiements():
    if request.method == 'POST':
        eleve_id = int(request.form.get('eleve_id'))
        rubrique_id = int(request.form.get('rubrique_id'))
        montant = float(request.form.get('montant_paye_cdf', request.form.get('montant_paye', 0)))
        mode_paiement = request.form.get('mode_paiement', 'Cash')
        
        num_recu = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        nouveau_p = Paiement(
            num_recu=num_recu,
            eleve_id=eleve_id,
            rubrique_id=rubrique_id,
            montant_paye_cdf=montant,
            montant_paye=montant,
            mode_paiement=mode_paiement
        )
        db.session.add(nouveau_p)
        db.session.commit()
        return redirect(url_for('ticket_pos', paiement_id=nouveau_p.id))
        
    eleves = Eleve.query.all()
    rubriques = RubriqueFrais.query.all()
    historique_paiements = Paiement.query.order_by(Paiement.date_paiement.desc()).all()
    return render_template('paiements.html', eleves=eleves, rubriques=rubriques, paiements=historique_paiements)

@app.route('/comptabilite', methods=['GET', 'POST'])
def comptabilite():
    config = ConfigurationQuota.query.first()
    if not config:
        config = ConfigurationQuota()
        db.session.add(config)
        db.session.commit()
        
    if request.method == 'POST':
        config.pct_salaires = float(request.form.get('pct_salaires', 45.0))
        config.pct_fonctionnement = float(request.form.get('pct_fonctionnement', 25.0))
        config.pct_promoteur = float(request.form.get('pct_promoteur', 15.0))
        config.pct_materiel = float(request.form.get('pct_materiel', 10.0))
        config.pct_reserve = float(request.form.get('pct_reserve', 5.0))
        db.session.commit()
        flash('Quotas mis à jour !', 'success')
        return redirect(url_for('comptabilite'))

    paiements_minerval = Paiement.query.join(RubriqueFrais).filter(RubriqueFrais.est_minerval == True).all()
    total_minerval = sum(p.montant_paye_cdf for p in paiements_minerval)
    
    return render_template('comptabilite.html', 
                           config=config, 
                           total_minerval=total_minerval,
                           part_salaires=total_minerval * (config.pct_salaires / 100),
                           part_fonctionnement=total_minerval * (config.pct_fonctionnement / 100),
                           part_promoteur=total_minerval * (config.pct_promoteur / 100),
                           part_materiel=total_minerval * (config.pct_materiel / 100),
                           part_reserve=total_minerval * (config.pct_reserve / 100))

@app.route('/ticket_pos/<int:paiement_id>')
def ticket_pos(paiement_id):
    paiement = Paiement.query.get_or_404(paiement_id)
    return render_template('ticket_pos.html', p=paiement, paiement=paiement)

@app.route('/seed')
def seed():
    db.drop_all()
    db.create_all()
    config = ConfigurationQuota()
    db.session.add(config)
    
    r1 = RubriqueFrais(nom="Frais d'Inscription", montant_cdf=75000.0, montant=75000.0, description="Inscription nouvel élève", sections_cibles="Toutes", options_cibles="Toutes", est_inscription=True)
    r2 = RubriqueFrais(nom="Minerval - 1er Trimestre", montant_cdf=375000.0, montant=375000.0, description="Frais T1", sections_cibles="Toutes", options_cibles="Toutes", est_minerval=True)
    r3 = RubriqueFrais(nom="Minerval - 2ème Trimestre", montant_cdf=375000.0, montant=375000.0, description="Frais T2", sections_cibles="Toutes", options_cibles="Toutes", est_minerval=True)
    r4 = RubriqueFrais(nom="Minerval - 3ème Trimestre", montant_cdf=375000.0, montant=375000.0, description="Frais T3", sections_cibles="Toutes", options_cibles="Toutes", est_minerval=True)
    
    db.session.add_all([r1, r2, r3, r4])
    db.session.commit()
    return "Base de données réinitialisée avec succès !"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
