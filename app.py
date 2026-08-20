import os
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
    __tablename__ = 'eleves'
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(20), unique=True, nullable=False)
    nom_complet = db.Column(db.String(100), nullable=False)
    sexe = db.Column(db.String(10), nullable=False)
    date_naissance = db.Column(db.String(20))
    lieu_naissance = db.Column(db.String(100))
    adresse = db.Column(db.String(200))
    section = db.Column(db.String(50), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    option = db.Column(db.String(50))
    nom_responsables = db.Column(db.String(100), nullable=False)
    lien_parente = db.Column(db.String(50))
    telephone_principal = db.Column(db.String(20), nullable=False)
    telephone_secondaire = db.Column(db.String(20))
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)
    
    paiements = db.relationship('Paiement', backref='eleve', lazy=True, cascade="all, delete-orphan")

class RubriqueFrais(db.Model):
    __tablename__ = 'rubriques_frais'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    section = db.Column(db.String(50))  # Optionnel : si un frais s'applique à une section précise

class Paiement(db.Model):
    __tablename__ = 'paiements'
    id = db.Column(db.Integer, primary_key=True)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleves.id'), nullable=False)
    rubrique_id = db.Column(db.Integer, db.ForeignKey('rubriques_frais.id'), nullable=True)
    montant = db.Column(db.Float, nullable=False)
    trimestre = db.Column(db.String(20))
    mode_paiement = db.Column(db.String(50), default='Espèces')
    date_paiement = db.Column(db.DateTime, default=datetime.utcnow)

    rubrique = db.relationship('RubriqueFrais', backref='paiements')


# ==========================================
# ROUTES DE L'APPLICATION
# ==========================================

@app.route('/')
def index():
    total_eleves = Eleve.query.count()
    total_recouvre = db.session.query(db.func.sum(Paiement.montant)).scalar() or 0.0
    derniers_paiements = Paiement.query.order_by(Paiement.date_paiement.desc()).limit(5).all()
    return render_template('index.html', total_eleves=total_eleves, total_recouvre=total_recouvre, derniers_paiements=derniers_paiements)


@app.route('/eleves')
def liste_eleves():
    nom_filter = request.args.get('nom', '').strip()
    section_filter = request.args.get('section', '')
    classe_filter = request.args.get('classe', '').strip()
    statut_filter = request.args.get('statut', '')

    query = Eleve.query

    # Filtre par nom complet
    if nom_filter:
        query = query.filter(Eleve.nom_complet.ilike(f"%{nom_filter}%"))
    if section_filter:
        query = query.filter(Eleve.section == section_filter)
    if classe_filter:
        query = query.filter(Eleve.classe.ilike(f"%{classe_filter}%"))

    eleves_db = query.order_by(Eleve.nom_complet.asc()).all()
    rubriques = RubriqueFrais.query.all()
    total_frais_fixe = sum(r.montant for r in rubriques)

    eleves_data = []
    for e in eleves_db:
        total_paye = sum(p.montant for p in e.paiements)
        reste_a_payer = max(0.0, total_frais_fixe - total_paye)
        
        # Filtre selon le statut financier
        if statut_filter == 'paye' and total_paye == 0:
            continue
        if statut_filter == 'non_paye' and total_paye > 0:
            continue
        if statut_filter == 'en_regle' and reste_a_payer > 0:
            continue
        if statut_filter == 'dette' and reste_a_payer == 0:
            continue

        eleves_data.append({
            'obj': e,
            'total_paye': total_paye,
            'reste_a_payer': reste_a_payer,
            'total_du': total_frais_fixe
        })

    return render_template(
        'eleves.html', 
        eleves_data=eleves_data, 
        nom_sel=nom_filter,
        section_sel=section_filter, 
        classe_sel=classe_filter, 
        statut_sel=statut_filter
    )


@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        # Génération matricule automatique simple
        dernier_eleve = Eleve.query.order_by(Eleve.id.desc()).first()
        next_id = (dernier_eleve.id + 1) if dernier_eleve else 1
        matricule = f"CSC-{datetime.now().year}-{next_id:04d}"

        nouvel_eleve = Eleve(
            matricule=matricule,
            nom_complet=request.form.get('nom_complet'),
            sexe=request.form.get('sexe'),
            date_naissance=request.form.get('date_naissance'),
            lieu_naissance=request.form.get('lieu_naissance'),
            adresse=request.form.get('adresse'),
            section=request.form.get('section'),
            classe=request.form.get('classe'),
            option=request.form.get('option'),
            nom_responsables=request.form.get('nom_responsables'),
            lien_parente=request.form.get('lien_parente'),
            telephone_principal=request.form.get('telephone_principal'),
            telephone_secondaire=request.form.get('telephone_secondaire')
        )
        
        db.session.add(nouvel_eleve)
        db.session.commit()
        flash('Élève inscrit avec succès !', 'success')
        return redirect(url_for('liste_eleves'))

    return render_template('inscription.html')


@app.route('/paiement', methods=['GET', 'POST'])
def paiement():
    eleve_id = request.args.get('eleve_id')
    eleve_selectionne = Eleve.query.get(eleve_id) if eleve_id else None

    if request.method == 'POST':
        e_id = request.form.get('eleve_id')
        rubrique_id = request.form.get('rubrique_id')
        montant = float(request.form.get('montant', 0))
        trimestre = request.form.get('trimestre')
        mode = request.form.get('mode_paiement', 'Espèces')

        nouveau_p = Paiement(
            eleve_id=e_id,
            rubrique_id=rubrique_id if rubrique_id else None,
            montant=montant,
            trimestre=trimestre,
            mode_paiement=mode
        )
        db.session.add(nouveau_p)
        db.session.commit()
        
        flash('Paiement enregistré avec succès !', 'success')
        return redirect(url_for('imprimer_recu', type_recu='paiement', id_recu=nouveau_p.id))

    eleves = Eleve.query.order_by(Eleve.nom_complet.asc()).all()
    rubriques = RubriqueFrais.query.all()
    return render_template('paiement.html', eleves=eleves, rubriques=rubriques, eleve_selectionne=eleve_selectionne)


@app.route('/imprimer_recu/<type_recu>/<int:id_recu>')
def imprimer_recu(type_recu, id_recu):
    if type_recu == 'paiement':
        p = Paiement.query.get_or_404(id_recu)
        return render_template('recu_print.html', type='paiement', p=p, e=p.eleve, datetime_now=datetime.now().strftime('%d/%m/%Y %H:%M'))
    else:
        e = Eleve.query.get_or_404(id_recu)
        return render_template('recu_print.html', type='inscription', e=e, datetime_now=datetime.now().strftime('%d/%m/%Y %H:%M'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
