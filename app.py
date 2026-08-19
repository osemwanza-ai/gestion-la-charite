from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
import os
import io

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cle_secrete_complexe_la_charite")

# --- DATABASE CONFIGURATION ---
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

# --- MODELS ---
class FraisInscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    montant = db.Column(db.Float, nullable=False, default=0.0)

class RubriqueFrais(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    montant = db.Column(db.Float, nullable=False, default=0.0)

class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(20), unique=True, nullable=False)
    nom_complet = db.Column(db.String(100), nullable=False)
    sexe = db.Column(db.String(10), default="M")
    date_naissance = db.Column(db.String(20), default="")
    lieu_naissance = db.Column(db.String(100), default="")
    adresse = db.Column(db.String(200), default="")
    nom_responsables = db.Column(db.String(100), default="")
    lien_parente = db.Column(db.String(50), default="")
    telephone_principal = db.Column(db.String(20), default="")
    telephone_secondaire = db.Column(db.String(20), default="")
    section = db.Column(db.String(50), default="Maternelle")
    classe = db.Column(db.String(50), default="1ère")
    option = db.Column(db.String(100), default="")
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    eleve_id = db.Column(db.Integer, db.ForeignKey('eleve.id'), nullable=False)
    rubrique_id = db.Column(db.Integer, db.ForeignKey('rubrique_frais.id'), nullable=False)
    trimestre = db.Column(db.String(50), nullable=False)
    montant = db.Column(db.Float, nullable=False, default=0.0)
    mode_paiement = db.Column(db.String(50), default="Espèces")
    date_paiement = db.Column(db.DateTime, default=datetime.utcnow)
    
    rubrique = db.relationship('RubriqueFrais', lazy=True)
    eleve = db.relationship('Eleve', lazy=True)

# --- CREATION & AUTO-MIGRATION DES TABLES ---
with app.app_context():
    db.create_all()
    try:
        db.session.execute(text("ALTER TABLE paiement ADD COLUMN IF NOT EXISTS mode_paiement VARCHAR(50) DEFAULT 'Espèces';"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

# --- ROUTES ---
@app.route('/')
def index():
    try:
        total_eleves = db.session.query(Eleve).count()
        paiements = Paiement.query.all()
        frais_inscr = FraisInscription.query.first()
        montant_inscr = frais_inscr.montant if frais_inscr else 0.0

        total_recettes = sum(p.montant for p in paiements) + (total_eleves * montant_inscr)

        trimestres = ['1er Trimestre', '2ème Trimestre', '3ème Trimestre']
        stats_trimestres = {}

        for t in trimestres:
            p_trim = [p for p in paiements if p.trimestre == t]
            eleves_minerval = set(p.eleve_id for p in p_trim if p.rubrique and 'minerval' in p.rubrique.nom.lower())
            eleves_technique = set(p.eleve_id for p in p_trim if p.rubrique and p.rubrique.nom and 'minerval' not in p.rubrique.nom.lower())
            stats_trimestres[t] = {
                'minerval': len(eleves_minerval),
                'technique': len(eleves_technique)
            }

        return render_template('dashboard.html', total_eleves=total_eleves, total_recettes=total_recettes, stats_trimestres=stats_trimestres)
    except Exception as e:
        db.session.rollback()
        return f"Erreur Serveur : {str(e)}", 500

@app.route('/eleves')
def liste_eleves():
    eleves = Eleve.query.order_by(Eleve.date_inscription.desc()).all()
    return render_template('eleves.html', eleves=eleves)

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    frais = FraisInscription.query.first()
    if request.method == 'POST':
        try:
            annee = datetime.now().year
            dernier = Eleve.query.order_by(Eleve.id.desc()).first()
            nxt = (dernier.id + 1) if dernier else 1
            mat = f"CH-{annee}-{nxt:03d}"

            e = Eleve(
                matricule=mat,
                nom_complet=request.form.get('nom_complet', '').strip(),
                sexe=request.form.get('sexe', 'M'),
                date_naissance=request.form.get('date_naissance', ''),
                lieu_naissance=request.form.get('lieu_naissance', ''),
                adresse=request.form.get('adresse', ''),
                nom_responsables=request.form.get('nom_responsables', ''),
                lien_parente=request.form.get('lien_parente', ''),
                telephone_principal=request.form.get('telephone_principal', ''),
                telephone_secondaire=request.form.get('telephone_secondaire', ''),
                section=request.form.get('section', 'Maternelle'),
                classe=request.form.get('classe', '1ère'),
                option=request.form.get('option', '')
            )
            db.session.add(e)
            db.session.commit()
            flash(f"✅ Élève inscrit avec succès ({mat})", "success")
            return redirect(url_for('index'))
        except Exception as err:
            db.session.rollback()
            flash(f"⚠️ Erreur d'enregistrement : {str(err)}", "danger")

    return render_template('inscription.html', frais=frais)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'frais_inscription':
            m = float(request.form.get('montant', 0))
            f = FraisInscription.query.first()
            if f: f.montant = m
            else: db.session.add(FraisInscription(montant=m))
            db.session.commit()
            flash("Frais d'inscription mis à jour.", "success")
        elif action == 'ajouter_rubrique':
            r = RubriqueFrais(
                nom=request.form.get('nom', 'Rubrique'),
                montant=float(request.form.get('montant', 0))
            )
            db.session.add(r)
            db.session.commit()
            flash("Rubrique ajoutée.", "success")
        return redirect(url_for('admin'))
    return render_template('admin.html', frais_inscription=FraisInscription.query.first(), rubriques=RubriqueFrais.query.all())

@app.route('/paiement', methods=['GET', 'POST'])
@app.route('/paiement/<int:eleve_id>', methods=['GET', 'POST'])
def paiement(eleve_id=None):
    try:
        eleves = Eleve.query.order_by(Eleve.nom_complet.asc()).all()
        rubriques = RubriqueFrais.query.all()
        eleve_sel = Eleve.query.get(eleve_id) if eleve_id else None

        if request.method == 'POST':
            if 'select_eleve' in request.form:
                sel_id = request.form.get('eleve_id')
                if sel_id:
                    return redirect(url_for('paiement', eleve_id=int(sel_id)))
            elif eleve_sel and request.form.get('rubrique_id'):
                p = Paiement(
                    eleve_id=eleve_sel.id,
                    rubrique_id=int(request.form.get('rubrique_id')),
                    trimestre=request.form.get('trimestre', '1er Trimestre'),
                    montant=float(request.form.get('montant', 0)),
                    mode_paiement=request.form.get('mode_paiement', 'Espèces')
                )
                db.session.add(p)
                db.session.commit()
                flash("Paiement enregistré !", "success")
                return redirect(url_for('paiement', eleve_id=eleve_sel.id))

        historique = Paiement.query.filter_by(eleve_id=eleve_sel.id).order_by(Paiement.date_paiement.desc()).all() if eleve_sel else []
        return render_template('paiement.html', eleve=eleve_sel, eleves=eleves, rubriques=rubriques, historique=historique)
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur : {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/download/<type_rapport>')
def download_rapport(type_rapport):
    try:
        output = io.StringIO()
        output.write("Matricule;Nom Complet;Rubrique;Trimestre;Montant (FC);Date\n")
        paiements = Paiement.query.all()
        for p in paiements:
            mat = p.eleve.matricule if p.eleve else "-"
            nom = p.eleve.nom_complet if p.eleve else "-"
            rubrique = p.rubrique.nom if p.rubrique else "-"
            output.write(f"{mat};{nom};{rubrique};{p.trimestre};{p.montant};{p.date_paiement.strftime('%d/%m/%Y')}\n")
        
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8-sig'))
        mem.seek(0)
        return send_file(mem, mimetype='text/csv', as_attachment=True, download_name=f'rapport_{type_rapport}.csv')
    except Exception as e:
        flash(f"Erreur export : {str(e)}", "danger")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
