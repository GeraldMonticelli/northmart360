import org.apache.jena.rdf.model.*;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.vocabulary.RDF;

import java.io.FileOutputStream;

public class TestReasoner {

    public static void main(String[] args) throws Exception {

        Model explicit = ModelFactory.createDefaultModel();

        // TBox
        explicit.read(
            "../datasets/lubm/lubm/data/univ-bench.owl"
        );

        // ABox
        explicit.read(
            "../datasets/lubm/lubm/lubm-canonical.nt",
            "N-TRIPLES"
        );

        System.out.println(
            "Triples explicites : " + explicit.size()
        );

        // OWL Mini : beaucoup plus rapide que OWL Full
        Reasoner reasoner =
            ReasonerRegistry.getOWLMiniReasoner();

        InfModel inf =
            ModelFactory.createInfModel(reasoner, explicit);

        inf.prepare();

        System.out.println(
            "Graphe après raisonnement : " + inf.size()
        );

        // Matérialiser uniquement les nouveaux rdf:type inférés
        Model inferredOnly = ModelFactory.createDefaultModel();

        StmtIterator it = inf.listStatements(
            null,
            RDF.type,
            (RDFNode) null
        );

        while (it.hasNext()) {

            Statement s = it.nextStatement();

            // On ne garde que les triples qui n'existaient pas
            // dans le graphe original
            if (!explicit.contains(s)) {
                inferredOnly.add(s);
            }
        }

        System.out.println(
            "Nouveaux rdf:type inférés : " + inferredOnly.size()
        );

        // Écriture du graphe d'inférence
        try (FileOutputStream out =
                new FileOutputStream("lubm-inferred.nt")) {

            inferredOnly.write(out, "N-TRIPLES");
        }

        System.out.println("Créé : lubm-inferred.nt");
    }
}