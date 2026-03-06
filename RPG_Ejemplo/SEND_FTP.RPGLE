**FREE
ctl-opt dftactgrp(*no) actgrp(*new) option(*srcstmt : *nodebugio);

// Declaración del archivo de comandos FTP (Physical File QTEMP/FTPSRC)
dcl-f FTPSRC usage(*output) device(*disk) usropn;

dcl-s Host      char(30) inz('192.168.1.50');
dcl-s User      char(10) inz('USUARIO');
dcl-s Pass      char(10) inz('PASSWORD');
dcl-s RemoteDir char(50) inz('/home/transfer/facturas');
dcl-s LocalFile char(10) inz('FAC_DATA');

// --- Proceso Principal ---
exsr GenFtpScript;
exsr ExecuteFtp;
*inlr = *on;

// --------------------------------------------------
// Subrutina: Generar Script de comandos FTP
// --------------------------------------------------
begsr GenFtpScript;
    open FTPSRC;

    // 1. Credenciales
    writeFTPSRC(User);
    writeFTPSRC(Pass);

    // 2. Comandos de transferencia
    writeFTPSRC('ascii');
    writeFTPSRC('cd ' + %trim(RemoteDir));
    writeFTPSRC('put LIBPROD/' + %trim(LocalFile));
    writeFTPSRC('quit');

    close FTPSRC;
endsr;

// --------------------------------------------------
// Subrutina: Ejecutar el comando del Sistema
// --------------------------------------------------
begsr ExecuteFtp;
    dcl-s cmd char(200);
    
    // El clásico comando de AS400 para FTP interactivo/batch
    cmd = 'STRTCPFTP RMTSYS(''' + %trim(Host) + ''') +
           SRCF(QTEMP/FTPSRC) MBR(FTPMBR)';
           
    qcmdexc(cmd : %len(%trim(cmd)));
endsr;

// --------------------------------------------------
// Procedimiento auxiliar para escribir en el PF
// --------------------------------------------------
dcl-proc writeFTPSRC;
    dcl-pi *n;
        p_data char(80) const;
    end-pi;
    
    // Estructura del registro del PF (normalmente SRCSEQ, SRCDAT, SRCDTA)
    // Aquí simplificamos asumiendo un archivo plano
    FTPSRC_Record = p_data; 
    write FTPSRC;
end-proc;