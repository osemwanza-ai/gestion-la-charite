from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import openpyxl
from io import BytesIO
from datetime import datetime
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'app_database.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Eleve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    matricule = db.Column(db.String(50), unique=True, nullable=False)
    telephone_tuteur = db.Column(db.String(20), nullable=True)
    frais_total = db.Column(db.Float, default=0.0)

class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_heure = db.Column(db.String(50), nullable=False)
    nom_eleve = db.Column(db.String(100), nullable=False)
    classe = db.Column(db.String(50), nullable=False)
    type_frais = db.Column(db.String(50), nullable=False)
    montant = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def dashboard():
    total_eleves = Eleve.query.count()
    paiements = Paiement.query.all()
    total_recettes = sum(p.montant for p in paiements)
    return render_template('dashboard.html', total_eleves=total_eleves, total_recettes=total_recettes)

# ONGLET 1 : Page d'inscription uniquement
@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        nom = request.form.get('nom_complet')
        classe = request.form.get('classe')
        telephone = request.form.get('telephone_tuteur')
        frais = float(request.form.get('frais_total', 0))
        
        count = Eleve.query.count() + 1
        matricule = f"CHAR-{datetime.now().year}-{count:03d}"

        nouvel_eleve = Eleve(
            nom_complet=nom,
            classe=classe,
            matricule=matricule,
            telephone_tuteur=telephone,
            frais_total=frais
        )
        db.session.add(nouvel_eleve)
        db.session.commit()
        return redirect(url_for('eleves'))

    return render_template('inscription.html')

# ONGLET 2 : Repertoire des élèves & État de paiement
@app.route('/eleves')
def eleves():
    liste_eleves = Eleve.query.order_by(Eleve.nom_complet.asc()).all()
    donnees_eleves = []

    for el in liste_eleves:
        paiements_eleve = Paiement.query.filter_by(nom_eleve=el.nom_complet).all()
        total_paye = sum(p.montant for p in paiements_eleve)
        reste = el.frais_total - total_paye
        est_en_regle = reste <= 0 and el.frais_total > 0

        donnees_eleves.append({
            'matricule': el.matricule,
            'nom_complet': el.nom_complet,
            'classe': el.classe,
            'telephone': el.telephone_tuteur or '-',
            'frais_total': el.frais_total,
            'total_paye': total_paye,
            'reste': max(0, reste),
            'en_regle': est_en_regle
        })

    return render_template('eleves.html', eleves=donnees_eleves)

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

@app.route('/historique')
def historique():
    liste = Paiement.query.order_by(Paiement.id.desc()).all()
    return render_template('historique.html', paiements=liste)

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
