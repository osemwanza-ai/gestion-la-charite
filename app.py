@app.route('/paiements', methods=['GET', 'POST'])
def paiements():
    eleves_inscrits = Eleve.query.order_by(Eleve.nom_complet.asc()).all()
    frais_autorises = ConfigurationFrais.query.all()
    donnees_recu = None

    if request.method == 'POST':
        eleve_id = request.form.get('eleve_id')
        
        # SÉCURITÉ : Bloque si aucun élève n'est sélectionné ou si l'élève n'existe pas
        if not eleve_id:
            return "Erreur : Vous devez obligatoirement sélectionner un élève inscrit.", 400
            
        eleve = Eleve.query.get(eleve_id)
        if not eleve:
            return "Erreur : Cet élève n'est pas répertorié dans la base des inscriptions.", 400
        
        categorie = request.form.get('categorie_frais')
        trimestre = request.form.get('trimestre')
        motif = request.form.get('motif_detail')
        montant = float(request.form.get('montant', 0))
        date_actuelle = datetime.now().strftime("%d/%m/%Y %H:%M")

        nouveau_p = Paiement(
            date_heure=date_actuelle,
            eleve_id=eleve.id,
            nom_eleve=eleve.nom_complet,
            classe=eleve.classe,
            categorie_frais=categorie,
            trimestre=trimestre if categorie == 'MINERVAL' else '-',
            motif_detail=motif,
            montant=montant
        )
        db.session.add(nouveau_p)
        db.session.commit()

        donnees_recu = {
            'nom': eleve.nom_complet,
            'classe': eleve.classe,
            'categorie': categorie,
            'trimestre': trimestre,
            'montant': montant,
            'date_heure': date_actuelle
        }

    return render_template('paiements.html', eleves=eleves_inscrits, frais_liste=frais_autorises, recu=donnees_recu)
