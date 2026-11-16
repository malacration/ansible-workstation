when HTTP_REQUEST {
   # Other HTTP values can be added here 
   set requri "https://[HTTP::host][HTTP::uri]"
}

when ASM_REQUEST_DONE {
        #ASM::support_id está bugado e não exibe o último dígito. Não há correção conhecida. É necessário usar o ASM::vioation_data e exibir a variável com lindex para exibir apenas o campo do support_id
        set asm_violation_data [ASM::violation_data]
        set asm_support_id [lindex $asm_violation_data 1]
        set asm_violation [lindex $asm_violation_data 0]

        if { $asm_violation contains "ACCESS_FROM_MALICIOUS_IP" } { 
            set orientacao "<p style='text-align: justify;'>O endereço de IP através do qual você está tentando acessar esta página possui uma reputação suspeita.<br>
                                Se você acredita que o bloqueio é indevido, você pode solicitar uma reavaliação de reputação deste IP através do link <b><a href='https://www.brightcloud.com/tools/url-ip-lookup.php'>brightcloud.com/tools/url-ip-lookup.php</a></b>.<br>
                                Caso precise de ajuda para solicitar a reavaliação de reputação, clique no link ao lado para acessar nosso passo a passo detalhado >> <a href='https://www.tjro.jus.br/guia-reputacao-ip' target='_blank'>Guia para revisão de reputação de IP</a><br><br>
                            </p>"
        } else {
            set orientacao "<p style='text-align: justify;'>
                                Seu acesso a esta página foi bloqueado.<br>
                                Por favor, abra um chamado através do e-mail <strong><b>atendemais@tjro.jus.br</b></strong>, informando <b>'Acesso Bloqueado'</b> no assunto e os dados informados abaixo no corpo do e-mail.<br><br>
                            </p>"

        }        

      }

when ASM_REQUEST_BLOCKING {


        HTTP::header remove Content-Length
        HTTP::header insert "sid" $asm_support_id
        #HTTP::header insert "F5-Violation" $asm_violation
        set client_ip [IP::client_addr]
        set cabecalhos [HTTP::header names]
        set pais [whereis $client_ip country]


        set response "<!DOCTYPE html>
<html lang='pt-br'>
<head>
    <title>STIC - Página Bloqueada</title>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <meta http-equiv='PRAGMA' content='NO-CACHE'>
    <style>
        body {
            background-color: #e7e8e9;
            font-family: Tahoma, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }

        #content {
            background-color: #fff;
            border: 3px solid #aaa;
            border-radius: 8px;
            margin: 1em;
            padding: 1.5em;
            width: 90%;
            box-sizing: border-box;
        }

        .logo {
            width: 100%;
            max-width: 250px;
            height: auto;
            display: block;
            margin: 0 auto 1.5em auto;
        }

        h1 {
            font-size: 1.3em;
            font-weight: bold;
            color: #196390;
            text-align: center;
        }

        p {
            line-height: 1.6;
            text-align: left;
        }


        b {
            font-weight: normal;
            color: #196390;
        }


        strong {
            word-wrap: break-word;
        }


        @media (min-width: 768px) {
            #content {
                max-width: 700px;
                padding: 2em;
            }

            p {
                text-align: justify;
            }
        }
    </style>
</head>
<body>
    <div id='content'>
        <img class='logo' src='https://www.tjro.jus.br/templates/portal_tjro_helix_j5/images/presets/default/logo.png' alt='Logo do Tribunal de Justiça de Rondônia'>

        <h1>Página Bloqueada</h1>

        $orientacao

        <p>
            <b>Seu endereço de IP é:</b> <strong>$client_ip</strong><br>
            <b>País de origem do IP:</b> <strong>$pais</strong><br>
            <b>O endereço que você tentou acessar é:</b> <strong>$requri</strong><br><br>
            <b>Seu support ID é:</b> <strong>$asm_support_id</strong><br>
        </p>
    </div>
</body>
</html>"

        ASM::payload replace 0 [ASM::payload length] ""
        ASM::payload replace 0 0 $response

      }
