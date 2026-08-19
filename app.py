@app.route('/payer/<int:eleve_id>', methods=['GET', 'POST'])
def payer(eleve_id):
    eleve = Eleve.query.get_or_404(eleve_id)
    
    if request.method == 'POST':
        rubrique_id = request.form.get('rubrique_id')
        trimestre = request.form.get('trimestre') # ex: "1er Trimestre"
        montant_verse = float(request.form.get('montant'))
        
        rubrique = RubriqueFrais.query.get(rubrique_id)
        montant_fixe = rubrique.montant # ex: 55000 FC

        # 1. Calcul des paiements déjà effectués pour cet élève, cette rubrique et ce trimestre
        paiements_existants = Paiement.query.filter_by(
            eleve_id=eleve.id, 
            rubrique_id=rubrique_id, 
            trimestre=trimestre
        ).all()
        
        total_deja_paye = sum(p.montant for p in paiements_existants)
        reste_a_payer = montant_fixe - total_deja_paye

        # 2. Vérification du plafond
        if reste_a_payer <= 0:
            flash(f"⚠️ Le solde pour {rubrique.nom} ({trimestre}) est déjà totalement apuré (0 FC restant). Veuillez sélectionner le trimestre suivant.", "danger")
            return redirect(url_for('payer', eleve_id=eleve.id))

        if montant_verse > reste_a_payer:
            flash(f"⚠️ Le montant saisi ({montant_verse:,.0f} FC) dépasse le solde du {trimestre}. Le reste à payer est de {reste_a_payer:,.0f} FC. Si l'élève paie d'avance, veuillez enregistrer le surplus sur le trimestre suivant.", "warning")
            return redirect(url_for('payer', eleve_id=eleve.id))

        # 3. Validation et enregistrement si le montant est correct
        nouveau_paiement = Paiement(
            eleve_id=eleve.id,
            rubrique_id=rubrique_id,
            trimestre=trimestre,
            montant=montant_verse,
            date_paiement=datetime.now()
        )
        db.session.add(nouveau_paiement)
        db.session.commit()

        flash(f"✅ Paiement de {montant_verse:,.0f} FC enregistré avec succès. Reste à payer pour ce trimestre : {reste_a_payer - montant_verse:,.0f} FC.", "success")
        return redirect(url_for('fiche_eleve', eleve_id=eleve.id))

    return render_template('payer.html', eleve=eleve)
