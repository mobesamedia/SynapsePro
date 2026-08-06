"""Complete Terms/Privacy translations used by the onboarding WebView.

The onboarding language is selected before the add-on's global language is
saved, so this dialog needs all language variants at once.
"""

from __future__ import annotations


TERMS_TRANSLATIONS = {
    "en": {
        "title": "Terms of Service & Privacy Notice",
        "updated": "Last updated: July 2026",
        "html": """
<h4>1. Acceptance of Terms</h4>
<p>By installing and using SynapsePro (the “Add-On”), you agree to these Terms of Service. If you do not agree, please uninstall the Add-On.</p>
<h4>2. Software Provided “As Is”</h4>
<p>SynapsePro is a free, independently developed add-on provided without warranties of any kind, express or implied. The developer does not guarantee its functionality, reliability, accuracy, or fitness for a particular purpose.</p>
<p>The developer is not liable for data loss, errors, bugs, crashes, interruptions, or other damage arising from use of the software. <strong>You use it at your own risk.</strong></p>
<h4>3. Information Collected During Setup</h4>
<p>During initial setup, SynapsePro asks for the following information. These answers are required to configure and personalize the Add-On:</p>
<ul><li>Selected interface language</li><li>User category (for example, Medical Student or Programmer)</li><li>How you found SynapsePro</li><li>Selected color theme</li><li>Add-On and Anki version numbers</li></ul>
<p>This information is also sent to the developer and stored in a database hosted by Supabase, which processes it on the developer’s behalf. It is used to maintain the Add-On, understand how it is used, and prioritize improvements.</p>
<p>No directly identifying data such as your name, email address, Anki card contents, learning statistics, login credentials, or device identifiers is collected or linked to these answers.</p>
<h4>4. How Your Data Is Used</h4>
<p>Your answers are used to configure SynapsePro and to help prioritize features and languages. <strong>Your data is never sold or shared with third parties for their own purposes.</strong> Supabase acts only as the technical hosting provider.</p>
<h4>5. No Account Required</h4>
<p>SynapsePro does not require an account and does not collect login credentials, email addresses, or personal identifiers.</p>
<h4>6. Open Source & Transparency</h4>
<p>You may inspect the Add-On’s source code at any time. No hidden data collection beyond what is described here takes place.</p>
<h4>7. Changes to These Terms</h4>
<p>These terms may be updated when the Add-On changes. Continued use after an update constitutes acceptance of the revised terms.</p>
<h4>8. Contact</h4>
<p>Questions or concerns can be sent through the official Anki Add-On page or to the contact address provided there.</p>""",
    },
    "de": {
        "title": "Nutzungsbedingungen & Datenschutzhinweis",
        "updated": "Zuletzt aktualisiert: Juli 2026",
        "html": """
<h4>1. Zustimmung zu den Bedingungen</h4>
<p>Mit der Installation und Nutzung von SynapsePro (dem „Add-On“) stimmst du diesen Nutzungsbedingungen zu. Wenn du nicht zustimmst, deinstalliere das Add-On bitte.</p>
<h4>2. Bereitstellung „wie besehen“</h4>
<p>SynapsePro ist ein kostenloses, unabhängig entwickeltes Add-On und wird ohne ausdrückliche oder stillschweigende Gewährleistung bereitgestellt. Der Entwickler übernimmt keine Garantie für Funktion, Zuverlässigkeit, Richtigkeit oder Eignung für einen bestimmten Zweck.</p>
<p>Der Entwickler haftet nicht für Datenverlust, Fehler, Abstürze, Unterbrechungen oder andere Schäden, die aus der Nutzung entstehen. <strong>Die Nutzung erfolgt auf eigenes Risiko.</strong></p>
<h4>3. Bei der Einrichtung erfasste Angaben</h4>
<p>Bei der Ersteinrichtung fragt SynapsePro die folgenden Angaben ab. Sie sind erforderlich, um das Add-On einzurichten und zu personalisieren:</p>
<ul><li>Ausgewählte Oberflächensprache</li><li>Nutzerkategorie (zum Beispiel Medizinstudent oder Programmierer)</li><li>Wie du SynapsePro gefunden hast</li><li>Ausgewähltes Farbschema</li><li>Versionsnummern von Add-On und Anki</li></ul>
<p>Diese Angaben werden außerdem an den Entwickler übermittelt und in einer von Supabase gehosteten Datenbank gespeichert. Supabase verarbeitet sie im Auftrag des Entwicklers. Sie dienen der Wartung des Add-Ons, dem Verständnis seiner Nutzung und der Priorisierung von Verbesserungen.</p>
<p>Direkt identifizierende Daten wie Name, E-Mail-Adresse, Inhalte deiner Anki-Karten, Lernstatistiken, Zugangsdaten oder Gerätekennungen werden weder erfasst noch mit diesen Angaben verknüpft.</p>
<h4>4. Verwendung deiner Daten</h4>
<p>Deine Antworten werden zur Einrichtung von SynapsePro und zur Priorisierung von Funktionen und Sprachen verwendet. <strong>Deine Daten werden niemals verkauft oder für eigene Zwecke an Dritte weitergegeben.</strong> Supabase dient ausschließlich als technischer Hosting-Anbieter.</p>
<h4>5. Kein Konto erforderlich</h4>
<p>SynapsePro erfordert kein Konto und erfasst keine Zugangsdaten, E-Mail-Adressen oder persönlichen Kennungen.</p>
<h4>6. Open Source & Transparenz</h4>
<p>Du kannst den Quellcode des Add-Ons jederzeit einsehen. Es findet keine versteckte Datenerfassung statt, die über die hier beschriebenen Vorgänge hinausgeht.</p>
<h4>7. Änderungen dieser Bedingungen</h4>
<p>Diese Bedingungen können bei Änderungen am Add-On aktualisiert werden. Die weitere Nutzung nach einem Update gilt als Zustimmung zur überarbeiteten Fassung.</p>
<h4>8. Kontakt</h4>
<p>Fragen oder Bedenken kannst du über die offizielle Anki-Add-On-Seite oder an die dort angegebene Kontaktadresse senden.</p>""",
    },
    "es": {
        "title": "Términos de servicio y aviso de privacidad",
        "updated": "Última actualización: julio de 2026",
        "html": """
<h4>1. Aceptación de los términos</h4>
<p>Al instalar y utilizar SynapsePro (el «Complemento»), aceptas estos Términos de servicio. Si no estás de acuerdo, desinstala el Complemento.</p>
<h4>2. Software proporcionado «tal cual»</h4>
<p>SynapsePro es un complemento gratuito e independiente que se ofrece sin garantías de ningún tipo, expresas ni implícitas. El desarrollador no garantiza su funcionamiento, fiabilidad, exactitud ni idoneidad para un fin concreto.</p>
<p>El desarrollador no se responsabiliza de pérdidas de datos, errores, fallos, cierres, interrupciones ni otros daños derivados del uso del software. <strong>Lo utilizas bajo tu propia responsabilidad.</strong></p>
<h4>3. Información recopilada durante la configuración</h4>
<p>Durante la configuración inicial, SynapsePro solicita los siguientes datos. Las respuestas son necesarias para configurar y personalizar el Complemento:</p>
<ul><li>Idioma de la interfaz seleccionado</li><li>Categoría de usuario (por ejemplo, estudiante de Medicina o programador)</li><li>Cómo conociste SynapsePro</li><li>Tema de color seleccionado</li><li>Versiones del Complemento y de Anki</li></ul>
<p>Esta información también se envía al desarrollador y se almacena en una base de datos alojada por Supabase, que la procesa por cuenta del desarrollador. Se utiliza para mantener el Complemento, comprender su uso y priorizar mejoras.</p>
<p>No se recopilan ni vinculan a estas respuestas datos de identificación directa como tu nombre, correo electrónico, contenido de tarjetas de Anki, estadísticas de estudio, credenciales o identificadores del dispositivo.</p>
<h4>4. Uso de tus datos</h4>
<p>Tus respuestas se utilizan para configurar SynapsePro y ayudar a priorizar funciones e idiomas. <strong>Tus datos nunca se venden ni se comparten con terceros para sus propios fines.</strong> Supabase actúa únicamente como proveedor técnico de alojamiento.</p>
<h4>5. No se requiere cuenta</h4>
<p>SynapsePro no requiere una cuenta ni recopila credenciales, direcciones de correo electrónico o identificadores personales.</p>
<h4>6. Código abierto y transparencia</h4>
<p>Puedes consultar el código fuente del Complemento en cualquier momento. No existe ninguna recopilación oculta de datos aparte de la descrita aquí.</p>
<h4>7. Cambios en estos términos</h4>
<p>Estos términos pueden actualizarse cuando cambie el Complemento. Seguir usándolo tras una actualización implica aceptar la versión revisada.</p>
<h4>8. Contacto</h4>
<p>Puedes enviar preguntas o inquietudes mediante la página oficial del complemento de Anki o a la dirección de contacto indicada allí.</p>""",
    },
    "pt": {
        "title": "Termos de Serviço e Aviso de Privacidade",
        "updated": "Última atualização: julho de 2026",
        "html": """
<h4>1. Aceitação dos termos</h4>
<p>Ao instalar e usar o SynapsePro (o “Add-On”), você concorda com estes Termos de Serviço. Caso não concorde, desinstale o Add-On.</p>
<h4>2. Software fornecido “no estado em que se encontra”</h4>
<p>O SynapsePro é um add-on gratuito e desenvolvido de forma independente, fornecido sem garantias expressas ou implícitas. O desenvolvedor não garante funcionamento, confiabilidade, exatidão ou adequação a uma finalidade específica.</p>
<p>O desenvolvedor não se responsabiliza por perda de dados, erros, falhas, travamentos, interrupções ou outros danos decorrentes do uso do software. <strong>O uso é por sua conta e risco.</strong></p>
<h4>3. Informações coletadas durante a configuração</h4>
<p>Na configuração inicial, o SynapsePro solicita os dados abaixo. As respostas são necessárias para configurar e personalizar o Add-On:</p>
<ul><li>Idioma de interface selecionado</li><li>Categoria de usuário (por exemplo, estudante de Medicina ou programador)</li><li>Como você conheceu o SynapsePro</li><li>Tema de cores selecionado</li><li>Versões do Add-On e do Anki</li></ul>
<p>Esses dados também são enviados ao desenvolvedor e armazenados em um banco de dados hospedado pela Supabase, que os processa em nome do desenvolvedor. Eles são usados para manter o Add-On, entender seu uso e priorizar melhorias.</p>
<p>Dados de identificação direta, como nome, e-mail, conteúdo dos cartões do Anki, estatísticas de estudo, credenciais ou identificadores do dispositivo, não são coletados nem vinculados às respostas.</p>
<h4>4. Como seus dados são usados</h4>
<p>Suas respostas são usadas para configurar o SynapsePro e ajudar a priorizar recursos e idiomas. <strong>Seus dados nunca são vendidos nem compartilhados com terceiros para finalidades próprias.</strong> A Supabase atua apenas como provedora técnica de hospedagem.</p>
<h4>5. Nenhuma conta necessária</h4>
<p>O SynapsePro não exige conta e não coleta credenciais, endereços de e-mail ou identificadores pessoais.</p>
<h4>6. Código aberto e transparência</h4>
<p>Você pode consultar o código-fonte do Add-On a qualquer momento. Não há coleta oculta de dados além do que está descrito aqui.</p>
<h4>7. Alterações nestes termos</h4>
<p>Estes termos podem ser atualizados quando o Add-On mudar. Continuar usando-o após uma atualização constitui aceitação dos termos revisados.</p>
<h4>8. Contato</h4>
<p>Dúvidas ou preocupações podem ser enviadas pela página oficial do Add-On no Anki ou para o endereço de contato informado nela.</p>""",
    },
    "fr": {
        "title": "Conditions d’utilisation et avis de confidentialité",
        "updated": "Dernière mise à jour : juillet 2026",
        "html": """
<h4>1. Acceptation des conditions</h4>
<p>En installant et en utilisant SynapsePro (l’« extension »), vous acceptez les présentes conditions d’utilisation. Si vous ne les acceptez pas, veuillez désinstaller l’extension.</p>
<h4>2. Logiciel fourni « en l’état »</h4>
<p>SynapsePro est une extension gratuite développée de manière indépendante et fournie sans garantie expresse ou implicite. Le développeur ne garantit ni son fonctionnement, ni sa fiabilité, ni son exactitude, ni son adéquation à un usage particulier.</p>
<p>Le développeur ne peut être tenu responsable d’une perte de données, d’erreurs, de bogues, de plantages, d’interruptions ou de tout autre dommage résultant de l’utilisation du logiciel. <strong>Vous l’utilisez à vos propres risques.</strong></p>
<h4>3. Informations recueillies lors de la configuration</h4>
<p>Lors de la première configuration, SynapsePro demande les informations suivantes. Ces réponses sont nécessaires pour configurer et personnaliser l’extension :</p>
<ul><li>Langue d’interface choisie</li><li>Catégorie d’utilisateur (par exemple étudiant en médecine ou programmeur)</li><li>Façon dont vous avez découvert SynapsePro</li><li>Thème de couleurs choisi</li><li>Numéros de version de l’extension et d’Anki</li></ul>
<p>Ces informations sont également envoyées au développeur et stockées dans une base de données hébergée par Supabase, qui les traite pour son compte. Elles servent à maintenir l’extension, à comprendre son utilisation et à prioriser les améliorations.</p>
<p>Aucune donnée directement identifiante, telle que votre nom, votre adresse e-mail, le contenu de vos cartes Anki, vos statistiques d’apprentissage, vos identifiants de connexion ou ceux de votre appareil, n’est recueillie ni associée à ces réponses.</p>
<h4>4. Utilisation de vos données</h4>
<p>Vos réponses servent à configurer SynapsePro et à orienter les priorités concernant les fonctionnalités et les langues. <strong>Vos données ne sont jamais vendues ni communiquées à des tiers pour leurs propres finalités.</strong> Supabase intervient uniquement comme hébergeur technique.</p>
<h4>5. Aucun compte requis</h4>
<p>SynapsePro ne nécessite aucun compte et ne recueille ni identifiants de connexion, ni adresses e-mail, ni identifiants personnels.</p>
<h4>6. Code source ouvert et transparence</h4>
<p>Vous pouvez consulter le code source de l’extension à tout moment. Aucune collecte de données cachée autre que celle décrite ici n’a lieu.</p>
<h4>7. Modification des présentes conditions</h4>
<p>Ces conditions peuvent être mises à jour lorsque l’extension évolue. La poursuite de son utilisation après une mise à jour vaut acceptation des conditions révisées.</p>
<h4>8. Contact</h4>
<p>Vous pouvez adresser vos questions ou préoccupations via la page officielle de l’extension Anki ou à l’adresse de contact qui y figure.</p>""",
    },
    "vi": {
        "title": "Điều khoản dịch vụ & Thông báo quyền riêng tư",
        "updated": "Cập nhật lần cuối: tháng 7 năm 2026",
        "html": """
<h4>1. Chấp nhận điều khoản</h4>
<p>Bằng việc cài đặt và sử dụng SynapsePro (“Tiện ích”), bạn đồng ý với các Điều khoản dịch vụ này. Nếu không đồng ý, vui lòng gỡ cài đặt Tiện ích.</p>
<h4>2. Phần mềm được cung cấp “nguyên trạng”</h4>
<p>SynapsePro là tiện ích miễn phí, được phát triển độc lập và được cung cấp không kèm bất kỳ bảo đảm rõ ràng hay ngụ ý nào. Nhà phát triển không bảo đảm về chức năng, độ tin cậy, độ chính xác hoặc sự phù hợp cho một mục đích cụ thể.</p>
<p>Nhà phát triển không chịu trách nhiệm đối với mất dữ liệu, lỗi, sự cố, gián đoạn hoặc thiệt hại khác phát sinh từ việc sử dụng phần mềm. <strong>Bạn tự chịu rủi ro khi sử dụng.</strong></p>
<h4>3. Thông tin được thu thập khi thiết lập</h4>
<p>Trong lần thiết lập đầu tiên, SynapsePro yêu cầu các thông tin dưới đây. Câu trả lời là cần thiết để cấu hình và cá nhân hóa Tiện ích:</p>
<ul><li>Ngôn ngữ giao diện đã chọn</li><li>Nhóm người dùng (ví dụ: sinh viên Y khoa hoặc lập trình viên)</li><li>Bạn biết đến SynapsePro bằng cách nào</li><li>Chủ đề màu đã chọn</li><li>Số phiên bản của Tiện ích và Anki</li></ul>
<p>Thông tin này cũng được gửi cho nhà phát triển và lưu trong cơ sở dữ liệu do Supabase lưu trữ, thay mặt nhà phát triển xử lý dữ liệu. Thông tin được dùng để duy trì Tiện ích, hiểu cách sử dụng và ưu tiên cải tiến.</p>
<p>Không thu thập hoặc liên kết với câu trả lời bất kỳ dữ liệu nhận dạng trực tiếp nào như tên, địa chỉ email, nội dung thẻ Anki, thống kê học tập, thông tin đăng nhập hoặc mã nhận dạng thiết bị.</p>
<h4>4. Cách sử dụng dữ liệu</h4>
<p>Câu trả lời của bạn được dùng để cấu hình SynapsePro và giúp ưu tiên tính năng, ngôn ngữ. <strong>Dữ liệu của bạn không bao giờ được bán hoặc chia sẻ với bên thứ ba cho mục đích riêng của họ.</strong> Supabase chỉ đóng vai trò nhà cung cấp dịch vụ lưu trữ kỹ thuật.</p>
<h4>5. Không cần tài khoản</h4>
<p>SynapsePro không yêu cầu tài khoản và không thu thập thông tin đăng nhập, địa chỉ email hoặc mã nhận dạng cá nhân.</p>
<h4>6. Mã nguồn mở & Minh bạch</h4>
<p>Bạn có thể kiểm tra mã nguồn của Tiện ích bất cứ lúc nào. Không có hoạt động thu thập dữ liệu ẩn nào ngoài nội dung được mô tả tại đây.</p>
<h4>7. Thay đổi điều khoản</h4>
<p>Các điều khoản này có thể được cập nhật khi Tiện ích thay đổi. Việc tiếp tục sử dụng sau khi cập nhật đồng nghĩa với chấp nhận điều khoản đã sửa đổi.</p>
<h4>8. Liên hệ</h4>
<p>Bạn có thể gửi câu hỏi hoặc mối quan ngại qua trang Tiện ích Anki chính thức hoặc địa chỉ liên hệ được nêu tại đó.</p>""",
    },
    "hi": {
        "title": "सेवा की शर्तें और गोपनीयता सूचना",
        "updated": "अंतिम अपडेट: जुलाई 2026",
        "html": """
<h4>1. शर्तों की स्वीकृति</h4>
<p>SynapsePro (“ऐड-ऑन”) को इंस्टॉल और उपयोग करके आप इन सेवा शर्तों से सहमत होते हैं। यदि आप सहमत नहीं हैं, तो कृपया ऐड-ऑन अनइंस्टॉल करें।</p>
<h4>2. सॉफ़्टवेयर “जैसा है” उपलब्ध</h4>
<p>SynapsePro एक मुफ़्त, स्वतंत्र रूप से विकसित ऐड-ऑन है और इसे किसी भी स्पष्ट या निहित वारंटी के बिना उपलब्ध कराया जाता है। डेवलपर इसकी कार्यक्षमता, विश्वसनीयता, सटीकता या किसी विशेष उद्देश्य के लिए उपयुक्तता की गारंटी नहीं देता।</p>
<p>सॉफ़्टवेयर के उपयोग से होने वाली डेटा हानि, त्रुटि, बग, क्रैश, रुकावट या अन्य क्षति के लिए डेवलपर उत्तरदायी नहीं है। <strong>आप इसका उपयोग अपने जोखिम पर करते हैं।</strong></p>
<h4>3. सेटअप के दौरान एकत्र जानकारी</h4>
<p>पहले सेटअप में SynapsePro नीचे दी गई जानकारी माँगता है। ऐड-ऑन को कॉन्फ़िगर और व्यक्तिगत बनाने के लिए ये उत्तर आवश्यक हैं:</p>
<ul><li>चुनी गई इंटरफ़ेस भाषा</li><li>उपयोगकर्ता श्रेणी (उदाहरण: मेडिकल छात्र या प्रोग्रामर)</li><li>आपको SynapsePro के बारे में कैसे पता चला</li><li>चुनी गई रंग थीम</li><li>ऐड-ऑन और Anki के संस्करण नंबर</li></ul>
<p>यह जानकारी डेवलपर को भी भेजी जाती है और Supabase द्वारा होस्ट किए गए डेटाबेस में रखी जाती है। Supabase इसे डेवलपर की ओर से प्रोसेस करता है। इसका उपयोग ऐड-ऑन के रखरखाव, उसके उपयोग को समझने और सुधारों को प्राथमिकता देने के लिए होता है।</p>
<p>आपका नाम, ईमेल पता, Anki कार्ड की सामग्री, अध्ययन आँकड़े, लॉगिन विवरण या डिवाइस पहचानकर्ता जैसी सीधे पहचान बताने वाली जानकारी न तो एकत्र की जाती है और न इन उत्तरों से जोड़ी जाती है।</p>
<h4>4. आपके डेटा का उपयोग</h4>
<p>आपके उत्तर SynapsePro को कॉन्फ़िगर करने और सुविधाओं व भाषाओं को प्राथमिकता देने में मदद के लिए उपयोग होते हैं। <strong>आपका डेटा कभी बेचा नहीं जाता और न ही तीसरे पक्ष को उनके अपने उद्देश्यों के लिए दिया जाता है।</strong> Supabase केवल तकनीकी होस्टिंग प्रदाता है।</p>
<h4>5. खाते की आवश्यकता नहीं</h4>
<p>SynapsePro के लिए खाते की आवश्यकता नहीं है और यह लॉगिन विवरण, ईमेल पता या व्यक्तिगत पहचानकर्ता एकत्र नहीं करता।</p>
<h4>6. ओपन सोर्स और पारदर्शिता</h4>
<p>आप किसी भी समय ऐड-ऑन का स्रोत कोड देख सकते हैं। यहाँ बताए गए संग्रह के अतिरिक्त कोई छिपा डेटा संग्रह नहीं होता।</p>
<h4>7. इन शर्तों में बदलाव</h4>
<p>ऐड-ऑन में बदलाव होने पर ये शर्तें अपडेट की जा सकती हैं। अपडेट के बाद उपयोग जारी रखना संशोधित शर्तों की स्वीकृति माना जाएगा।</p>
<h4>8. संपर्क</h4>
<p>प्रश्न या चिंताएँ आधिकारिक Anki ऐड-ऑन पृष्ठ के माध्यम से या वहाँ दिए गए संपर्क पते पर भेजी जा सकती हैं।</p>""",
    },
    "ko": {
        "title": "서비스 약관 및 개인정보 보호 안내",
        "updated": "최종 업데이트: 2026년 7월",
        "html": """
<h4>1. 약관 동의</h4>
<p>SynapsePro(이하 “애드온”)를 설치하고 사용하면 본 서비스 약관에 동의하는 것으로 간주됩니다. 동의하지 않으면 애드온을 삭제해 주세요.</p>
<h4>2. “있는 그대로” 제공되는 소프트웨어</h4>
<p>SynapsePro는 독립적으로 개발된 무료 애드온이며 명시적·묵시적 보증 없이 제공됩니다. 개발자는 기능, 신뢰성, 정확성 또는 특정 목적에 대한 적합성을 보장하지 않습니다.</p>
<p>개발자는 소프트웨어 사용으로 발생하는 데이터 손실, 오류, 버그, 충돌, 중단 또는 기타 손해에 책임을 지지 않습니다. <strong>사용에 따른 위험은 사용자 본인이 부담합니다.</strong></p>
<h4>3. 초기 설정 중 수집되는 정보</h4>
<p>SynapsePro는 최초 설정 시 다음 정보를 요청합니다. 애드온을 설정하고 개인화하려면 답변이 필요합니다.</p>
<ul><li>선택한 인터페이스 언어</li><li>사용자 범주(예: 의대생 또는 프로그래머)</li><li>SynapsePro를 알게 된 경로</li><li>선택한 색상 테마</li><li>애드온 및 Anki 버전 번호</li></ul>
<p>이 정보는 개발자에게 전송되며 개발자를 대신해 데이터를 처리하는 Supabase의 호스팅 데이터베이스에 저장됩니다. 애드온 유지관리, 사용 방식 파악 및 개선 우선순위 결정에 사용됩니다.</p>
<p>이름, 이메일 주소, Anki 카드 내용, 학습 통계, 로그인 정보 또는 기기 식별자처럼 사용자를 직접 식별하는 정보는 수집되지 않으며 답변과 연결되지 않습니다.</p>
<h4>4. 데이터 사용 방식</h4>
<p>답변은 SynapsePro 설정과 기능·언어의 우선순위 결정에 사용됩니다. <strong>데이터는 판매되지 않으며 제3자의 자체 목적을 위해 공유되지 않습니다.</strong> Supabase는 기술 호스팅 제공업체로만 역할합니다.</p>
<h4>5. 계정 불필요</h4>
<p>SynapsePro는 계정을 요구하지 않으며 로그인 정보, 이메일 주소 또는 개인 식별자를 수집하지 않습니다.</p>
<h4>6. 오픈 소스 및 투명성</h4>
<p>언제든 애드온의 소스 코드를 확인할 수 있습니다. 여기에 설명된 내용 외의 숨겨진 데이터 수집은 없습니다.</p>
<h4>7. 약관 변경</h4>
<p>애드온이 변경되면 본 약관도 업데이트될 수 있습니다. 업데이트 후 계속 사용하면 개정된 약관에 동의한 것으로 간주됩니다.</p>
<h4>8. 문의</h4>
<p>질문이나 우려 사항은 공식 Anki 애드온 페이지 또는 해당 페이지에 기재된 연락처로 보내 주세요.</p>""",
    },
    "zh": {
        "title": "服务条款与隐私声明",
        "updated": "最后更新：2026 年 7 月",
        "html": """
<h4>1. 接受条款</h4>
<p>安装并使用 SynapsePro（以下简称“插件”）即表示你同意本服务条款。如不同意，请卸载本插件。</p>
<h4>2. 软件按“现状”提供</h4>
<p>SynapsePro 是一款免费、独立开发的插件，不提供任何明示或默示担保。开发者不保证其功能、可靠性、准确性或特定用途适用性。</p>
<p>对于使用软件造成的数据丢失、错误、漏洞、崩溃、中断或其他损失，开发者不承担责任。<strong>使用风险由你自行承担。</strong></p>
<h4>3. 初始设置期间收集的信息</h4>
<p>首次设置时，SynapsePro 会询问以下信息。为配置和个性化插件，你必须回答这些问题：</p>
<ul><li>所选界面语言</li><li>用户类别（例如医学生或程序员）</li><li>你了解 SynapsePro 的途径</li><li>所选配色主题</li><li>插件与 Anki 的版本号</li></ul>
<p>这些信息也会发送给开发者，并存储在由 Supabase 托管的数据库中；Supabase 代表开发者处理这些数据。数据用于维护插件、了解使用方式并确定改进优先级。</p>
<p>不会收集姓名、电子邮件地址、Anki 卡片内容、学习统计、登录凭据或设备标识符等可直接识别身份的数据，也不会将其与上述回答关联。</p>
<h4>4. 数据用途</h4>
<p>你的回答用于配置 SynapsePro，并帮助确定功能和语言的优先级。<strong>你的数据绝不会被出售，也不会为了第三方自身目的而与其共享。</strong>Supabase 仅作为技术托管服务商。</p>
<h4>5. 无需账户</h4>
<p>SynapsePro 无需创建账户，也不收集登录凭据、电子邮件地址或个人标识符。</p>
<h4>6. 开源与透明</h4>
<p>你可以随时查看插件源代码。除本文所述内容外，不会进行任何隐藏的数据收集。</p>
<h4>7. 条款变更</h4>
<p>插件发生变化时，本条款可能更新。更新后继续使用即表示接受修订后的条款。</p>
<h4>8. 联系方式</h4>
<p>如有问题或疑虑，可通过官方 Anki 插件页面或页面中提供的联系方式提出。</p>""",
    },
}
